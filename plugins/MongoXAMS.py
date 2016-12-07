import time

import numpy as np
import pymongo
import snappy

from pax.datastructure import Event, Pulse, EventProxy
from pax import plugin, units


class MongoXAMSBase:
    
    def startup(self):
        self.mongo_time_unit = int(self.config.get('mongo_time_unit', 10 * units.ns))
        self.only_from_channels = self.config.get('only_from_channels', None)
        self.dt = self.config['sample_duration']

        self.log.debug("Connecting to %s" % self.config['address'])
        try:
            self.client = pymongo.MongoClient(self.config['address'])
            database_name = self.config.get('input_name', self.config.get('database', 'xamsdata'))
            self.database = self.client[database_name]
            self.collection = self.database[self.config['collection']]
        except pymongo.errors.ConnectionFailure as e:
            self.log.fatal("Cannot connect to database")
            self.log.exception(e)
            raise

        self.collection.create_index([('time', pymongo.ASCENDING)], background=True)

        self.pulses = []
        self.current_time = -1
        self.events_built = 0
        super().startup()

    def events_from_mongo_docs(self, pulse_docs, flush=False):
        """Yields pax events from Mongo pulse documents.
        Assumes all pulses belonging to a single event start and end at the same time.
        :param pulse_docs: iterable yielding pulse docs in ascending time order
        :param flush: set to true to cause the last event to flush out. Leave to false if you're not sure you have
        all the pulses for the last event in pulse_docs.
        """
        for pulse_doc in pulse_docs:

            if self.only_from_channels is not None:
                if pulse_doc['channel'] not in self.only_from_channels:
                    continue

            if pulse_doc['time'] != self.current_time:
                if len(self.pulses):
                    yield self.make_event()
                self.current_time = pulse_doc['time'] * self.dt

            # Fetch raw data from document
            data = snappy.decompress(pulse_doc['data'])

            self.pulses.append(Pulse(left=0,
                                     raw_data=np.fromstring(data, dtype="<i2"),
                                     channel=pulse_doc['channel']))

        if flush and len(self.pulses):
            yield self.make_event()

    def make_event(self):
        """Send the event from the currently processed pulses, then prepare for the next event
        """
        event = Event(n_channels=self.config['n_channels'],
                      start_time=self.current_time,
                      sample_duration=self.dt,
                      stop_time=self.current_time + self.dt * len(self.pulses[0].raw_data),
                      pulses=self.pulses,
                      event_number=self.events_built)
        self.events_built += 1
        self.pulses = []
        return event


class MongoDBInputOnline(MongoXAMSBase, plugin.InputPlugin):

    def startup(self):
        super().startup()

    def get_events(self):
        last_pulse_time = -1
        last_time_searched = 0
        insufficient_last_time = False

        # Keep behind last pulse in the DB to avoid problems if insertion is slightly asynchonous
        acquisition_delay = self.config.get('acquisition_delay_sec', 3) * units.s / self.mongo_time_unit

        # nothing_last_time = False
        # last_query_time = None
        # also_less_last_time = False
        minimum_query_time = self.config.get('minimum_query_time_seconds', 3) * units.s / self.mongo_time_unit

        done = False
        while done is False:

            last_pulse_list = list(self.collection.find().sort('_id', direction=pymongo.DESCENDING).limit(1))
            if not len(last_pulse_list):
                raise ValueError("No pulses in database?")
            
            last_pulse_time = last_pulse_list[0]['time']
            next_time_to_search = last_pulse_time - acquisition_delay
    
            data_range_to_query = next_time_to_search - last_time_searched

            time_to_sleep = minimum_query_time - data_range_to_query
            time_to_sleep *= self.mongo_time_unit / units.s
            if time_to_sleep > 0:
                time_to_sleep += 5                
                if insufficient_last_time:
                    # Still not enough data -- we must be nearing the end of run. Fetch all data!
                    next_time_to_search = last_pulse_time + 1000
                    done = True
                else:
                    self.log.info("Insufficient data remaining, sleeping %0.1f sec, then retrying" % (time_to_sleep))
                    time.sleep(time_to_sleep)
                    insufficient_last_time = True
                    continue

            insufficient_last_time = False

            self.log.info("Searching after %0.3f mongos until %0.4f mongos" % (last_time_searched, next_time_to_search))
            cursor = self.collection.find({"time": {"$gte": last_time_searched, 
                                                    "$lt": next_time_to_search}})
            cursor = cursor.sort("time", pymongo.ASCENDING)
            self.log.info("Found %d pulses" % cursor.count())

            last_time_searched = next_time_to_search
            
            yield from self.events_from_mongo_docs(cursor, flush=done)        

"""
class MongoDBInputTriggered(plugin.InputPlugin, MongoXAMSBase):

    # Read triggered data produced by kodiaq with MongoDB output
    # This must be run after the data aquisition is finished.

    do_output_check = False

    def startup(self):
        MongoXAMSBase.startup(self)

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


class MongoDBInputTriggeredEncoder(plugin.TransformPlugin, MongoXAMSBase):
    do_input_check = False

    def transform_event(self, event_proxy):

        event_number = event_proxy.event_number
        trigger_time = event_proxy.data['trigger_time']

        cursor = self.collection.find({'time': trigger_time})

        event = list(self.events_from_mongo_docs(pulse_docs=cursor, flush=True))[0]
        event.event_number = event_number

        return event
"""
