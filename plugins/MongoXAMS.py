from pax import plugin, units
import numpy as np
import pymongo

import snappy
from bson.binary import Binary
from pax.datastructure import Event, Pulse, EventProxy


class MongoBase():
    
    def startup(self):
        self.log.debug("Connecting to %s" % self.config['address'])
        try:
            self.client = pymongo.MongoClient(self.config['address'])
            self.database = self.client[self.config['database']]
            self.collection = self.database[self.config['collection']]
        except pymongo.errors.ConnectionFailure as e:
            self.log.fatal("Cannot connect to database")
            self.log.exception(e)
            raise



class MongoDBInputTriggered(plugin.InputPlugin, MongoBase):

    """Read triggered data produced by kodiaq with MongoDB output

    This must be run after the data aquisition is finished.
    """
    do_output_check = False

    def startup(self):
        MongoBase.startup(self)

        # All of the channel pulses will have the same
        # time if they came from the same trigger.
        self.trigger_times = self.collection.distinct('time')
        self.number_of_events = len(self.trigger_times)

        if self.number_of_events == 0:
            raise RuntimeError("No events found... did you run the event builder?")
        self.log.info("Found %d events" % self.number_of_events)

    def total_number_events(self):
        return self.number_of_events

    def get_events(self):
        for i in range(len(self.trigger_times)):
            yield self.get_single_event(i)
        
    def get_single_event(self, event_number):
        if event_number > len(self.trigger_times) - 1:
            raise ValueError("Asked for event %d, but have only %d events..." % (event_number, len(self.trigger_times)))
            
        trigger_time = self.trigger_times[event_number]
        self.log.debug("Fetching trigger time %d", trigger_time)

        return EventProxy(event_number=event_number, data=dict(trigger_time=trigger_time), block_id=-1)



class MongoDBInputTriggeredEncoder(plugin.TransformPlugin, MongoBase):
    do_input_check = False

    def startup(self):
        MongoBase.startup(self)

        self.mongo_time_unit = int(self.config.get('mongo_time_unit', 10 * units.ns))
        self.only_from_channels = self.config.get('only_from_channels', None)

    def transform_event(self, event_proxy):
        event_number = event_proxy.event_number
        data = event_proxy.data
        trigger_time = data['trigger_time']

        cursor = self.collection.find({'time': trigger_time})
        self.log.debug("Found %d pulses", cursor.count())

        latest_time = []
        pulse_objects = []

        for j, pulse_doc in enumerate(cursor):
            self.log.debug("Fetching document %s" % repr(pulse_doc['_id']))
                           
            if self.only_from_channels is not None:
                if pulse_doc['channel'] not in self.config['only_from_channels']:
                    continue

            # Fetch raw data from document

            data = snappy.decompress(pulse_doc['data'])
            # Samples are stored as 16 bit numbers (i.e. 2 bytes).  Also
            # note that // is an integer divide.
            latest_time.append(trigger_time + len(data) // 2)

            pulse_objects.append(Pulse(left=0,
                                       raw_data=np.fromstring(data, dtype="<i2"),
                                       channel=pulse_doc['channel']))

        earliest_time = trigger_time * self.mongo_time_unit
        latest_time = max(latest_time) * self.mongo_time_unit

        self.log.debug("Building event in range [%d,%d]",
                       earliest_time,
                       latest_time)
        return Event(n_channels=self.config['n_channels'],
                     start_time=earliest_time,
                     sample_duration=self.config['sample_duration'],
                     stop_time=latest_time,
                     pulses=pulse_objects,
                     event_number=event_number)

