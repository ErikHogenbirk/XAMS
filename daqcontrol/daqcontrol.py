from collections import OrderedDict
import json
import os
import random
import datetime
import time
import threading
from queue import Queue, Empty

import pytz
import pymongo
import ptyprocess
import bottle as bt

from pax import core

prefab_ini_folder = 'ini'
kodiaq_location = '/home/xams/kodiaq/src/slave'
# Pax ini to use as template, TODO: config overrides can be included in 'processor' section of kodiaq ini
pax_ini_config_path = '/home/xams/xams/XAMS_daq_to_raw.ini'
# Directory in which to build data. TODO: conigure in ini as well, or even field on website
default_data_directory = '/home/xams/xams/data'

done_field_name = 'event_building_complete'

kodiaq_command_queue = Queue()
kodiaq_running = False
kodiaq_taking_data = False
timed_actions = []      # list of threading.Timer() objects that are waiting

# Connection to mongo: don't need to reinit this every time somebody refreshes the page
client = pymongo.MongoClient()
runs_collection = client['run']['runs']

the_page = """
<html>
<head>
<title>XAMS DAQ</title>
<style>
table, th, td {
    border: 1px solid black;
}
</style>
</head>

<body>
<h1>XAMS DAQ control</h1>

<span color='red'>{{message if message else ''}}</span>

<form method='POST' action='/process'>
Kodiaq Control:
% for action, possible in action_options.items():
    <input type="submit" name='action' {{'disabled' if not possible else ''}} value='{{action}}' />
% end
<br/>

Configuration:
<select name='ini' {{run_form_status}}/>
% for x in ininames:
    <option value={{x}}>{{x}}</option>
% end
</select>
<br/>

Stop after <input type='text' name='stop_after' size=5 {{run_form_status}}/> seconds (leave empty to run forever).<br/>
Repeat (forever) run after stopping <input type='checkbox' name='repeat' {{run_form_status}}/><br/>
Delete data from Mongo after done reading <input type='checkbox' name='delete_data' {{run_form_status}}/><br/>

Comments for new run:<br/>
<textarea name="comments" cols="40" rows="5" {{run_form_status}}>
{{default_comment}}
</textarea>
<br/>

<br/><br/><br/>

<h2>List of runs:</h2></br>
<table>
<tr> <td>Name</td> <td>Ini</td> <td>Start (UTC)</td> <td>Duration (min)</td>  <td>Events</td> <td>Comments</td> <td>Location</td> </tr>
% for r in rundocs:
<tr>
    <td>{{r['ini']['mongo']['collection']}}</td>
    <td>{{r['ini'].get('ini_template_name', '')}}</td>
    <td>{{r['start'].strftime('%Y/%m/%d %H:%M:%S')}}</td>
    <td>{{'%0.1f' % ((r['end'] - r['start']).total_seconds() / 60) if 'end' in r else 'Still running'}}</td>
    <td>{{r.get('events_built', '?')}}</td>
    <td>{{r['ini'].get('comments', '')}}</td>
    <td>{{r['ini'].get('data_folder', '?')}}</td>
</tr>
% end
</table>
</form>
</body>
</html>
"""


def main():
    # Start the kodiaq manager thread
    kodiaq_thread = threading.Thread(target=kodiaq_manager, args=(kodiaq_command_queue,))
    kodiaq_thread.start()

    # Start the pax manager thread. This does not accept commands.
    pax_thread = threading.Thread(target=pax_manager)
    pax_thread.start()

    bt.run(host='localhost', port=8080)


def kodiaq_manager(q):
    """Thread that babysits kodiaq (main thread is listening for HTTP requests)
    q: queue to receives messages. Message is either 'start', which triggers starting kodiaq, or any string which will
    be passed to kodiaq verbatim.
    """
    kodiaq = None

    # I don't see how we can do STDOUT redirection with ptyprocess
    # read is blocking, so we need a slurper thread:
    def slurper(kodiaq):
        while True:
            if kodiaq is None or not kodiaq.isalive():
                print("[kodiaqmanager] Kodiaq not (yet) alive")
                time.sleep(1)
                continue
            try:
                print(kodiaq.read(10), end="")
            except EOFError:
                # Kodiaq is about to quit
                print("[kodiaqmanager] Got EOF when reading kodiaq's output, probably you're shutting down kodiaq?")
                break

    while True:
        try:
            message = q.get_nowait()

        except Empty:
            time.sleep(1)
            continue

        if kodiaq is None:
            if message == 'start':
                print("[kodiaqmanager] Starting kodiaq")
                cwd = os.getcwd()
                os.chdir(kodiaq_location)

                kodiaq = ptyprocess.PtyProcessUnicode.spawn([os.path.join(kodiaq_location, 'koSlave')], echo=True)

                os.chdir(cwd)
                threading.Thread(target=slurper, args=(kodiaq,)).start()
            else:
                raise ValueError("[kodiaqmanager] Invalid message %s while kodiaq not running" % message)

        else:
            print("[kodiaqmanager] Sending keystroke >%s< to kodiaq" % message)
            kodiaq.write(message)

            if message == 'q':
                kodiaq.wait()
                kodiaq = None


def start_run(ini, stop_after=0, comments='', repeat=False, delete_data=False):
    global kodiaq_taking_data, timed_actions

    #TODO: Insert collection name and comments in ini, pass ini to kodiaq
    with open(os.path.join(prefab_ini_folder, ini), mode='r') as data_file:
        ini_data = json.load(data_file)

    ini_data['mongo']['collection'] = datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S')
    ini_data['comments'] = comments
    ini_data['ini_template_name'] = ini[:-4]
    ini_data['delete_data'] = delete_data

    # Would be chill if we could adapt path on website, then do e.g
    # ini_data['pax_config_override'].setdefault({})
    # ini_data['pax_config_override']['pax'].setdefault({})
    # ini_data['pax_config_override']['pax']['output_name'] = output_folder
    with open(os.path.join(kodiaq_location, 'DAQConfig.ini'), mode='w') as outfile:
        json.dump(ini_data, outfile)

    kodiaq_command_queue.put('s')
    kodiaq_taking_data = True

    if stop_after:
        print("[daqcontrol] Scheduling run stop after %d seconds" % stop_after)
        t = threading.Timer(stop_after, stop_run)
        t.start()
        timed_actions.append(t)
    if repeat:
        restart_after = stop_after + 10
        print("[daqcontrol] Scheduling run restart after %d seconds" % restart_after)

        # Start the run 10 seconds after we stop
        t = threading.Timer(restart_after,
                            start_run,
                            kwargs=dict(ini=ini, stop_after=stop_after, comments=comments, repeat=repeat))
        t.start()
        timed_actions.append(t)

    message = "[daqcontrol] Started run with ini %s, stop_after %s, comments %s, repeat %s" % (ini, stop_after, comments, repeat)
    return message


def stop_run():
    global kodiaq_taking_data
    print("[daqcontrol] Stopping run")
    kodiaq_command_queue.put('p')
    kodiaq_taking_data = False


def pax_manager():
    while True:
        # Get all runs for which events have not been built yet
        runs_todo = list(runs_collection.find({done_field_name: {'$exists': False}}))

        if not runs_todo:
            print("[paxmanager] No more runs to process, waiting a while...")
            time.sleep(10)
            continue

        for run_doc in runs_todo:
            run_name = run_doc['name']

            # Get possible pax config overrides from the run doc
            conf_override = run_doc.get('processor', {})

            # Set the input (mongo collection) and output (folder to write folder of zips to)
            conf_override.setdefault('pax', {})
            conf_override['pax']['input_name'] = run_name
            output_folder = run_doc['ini'].get('data_folder', default_data_directory)
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            conf_override['pax']['output_name'] = os.path.join(output_folder, run_name)

            # WARNING this will delete your data!
            conf_override.setdefault('MongoXAMS', {})
            delete_data = run_doc['ini'].get('delete_data', False)
            if delete_data:
                print("Warning: I will be deleting your data!!!")
            conf_override['MongoXAMS']['delete_data'] = delete_data
            # Read which channels are enabled based on runs db
            try:
                register_list = run_doc['ini']['registers']
                channels_enabled_dict = next(item for item in register_list if item["register"] == "8120")
                binary_string = bin(int(channels_enabled_dict['value'], 16))[2:]
                channels_enabled_list = [ch_n for ch_n, enabled in enumerate(reversed(binary_string)) if enabled == '1']
            except:
                print('WARNING did not correctly read channel enable mask, using [0,3]...')
                channels_enabled_list = [0, 3]
            # DEBUG check which channels are read
            print('Read enabled channels from run doc: ', channels_enabled_list)
            conf_override['MongoXAMS']['only_from_channels'] = channels_enabled_list

            print("[paxmanager] Starting pax to process run %s, output to %s" % (run_name, output_folder))
            mypax = core.Processor(config_paths=pax_ini_config_path,
                                   config_dict=conf_override)
            mypax.run()

            del mypax
            print("Pax is done!")

            runs_collection.find_one_and_update({'name': run_name},
                                                {'$set': {done_field_name: True}})

            print("[paxmanager] Temporary nap to prevent infinite print or something")
            time.sleep(3)


@bt.route('/')
def view_page():
    rundocs = list(runs_collection.find().sort('start', pymongo.DESCENDING))

    can_start_run = kodiaq_running and not kodiaq_taking_data
    now = datetime.datetime.now()
    default_comment = ''

    if can_start_run and random.random() < 1/80:
        default_comment = random.choice(['Greatest run ever!',
                                         "Let's take another run\nthat would be fun"])
    elif now.hour > 23 or now.hour < 4:
        default_comment = "Dude, are you controlling XAMS in the middle of the night??"

    return bt.template(the_page,
                       rundocs=rundocs,
                       message=bt.request.query.message,
                       default_comment=default_comment,
                       run_form_status='' if can_start_run else 'disabled',
                       ininames=[x for x in os.listdir(prefab_ini_folder) if x.endswith('.ini')],
                       action_options=OrderedDict([('boot_kodiaq', not kodiaq_running),
                                                   ('start_run', can_start_run),
                                                   ('stop_run', (kodiaq_running and kodiaq_taking_data)),
                                                   ('quit_kodiaq', kodiaq_running and not kodiaq_taking_data)]))



@bt.route('/process', method='POST')
def process():
    global kodiaq_running, kodiaq_taking_data
    action = bt.request.forms['action']

    # If any manual command is received, all queued commands are canceled
    global timed_actions
    for t in timed_actions:
        print("Canceled a queued command due to a manual one being received")
        t.cancel()
    timed_actions = []

    message_page = """
    <html><head><meta http-equiv="refresh" content="1;url=/" /></head>
    <body>
    <h2>{{message}}</h2><br/>
    <p>Going back to main page in 1 second...</p>
    </body>
    </html>
    """
    if action == 'boot_kodiaq':
        if kodiaq_running:
            message = "Can't boot kodiaq, it's already running."
        else:
            kodiaq_command_queue.put('start')
            kodiaq_running = True
            message = "Started kodiaq"

    elif action == 'quit_kodiaq':
        if kodiaq_taking_data:
            message = "First stop the run"
        elif not kodiaq_running:
            message = "Kodiaq isn't running, can't start it"
        else:
            kodiaq_command_queue.put('q')
            kodiaq_running = False
            message = "Shutting down kodiaq"

    elif action == 'stop_run':
        if not kodiaq_running:
            message = "Can't stop run, kodiaq is not even running"
        elif not kodiaq_taking_data:
            message = "Can't stop run, no run in progress"
        else:
            stop_run()
            message = "Stopped the run."

    elif action == 'start_run':
        if not kodiaq_running:
            message = "Can't start run, kodiaq not yet running"
        elif kodiaq_taking_data:
            message = "Can't start run, already in progress"
        else:
            # Get data from the form
            comments = bt.request.forms['comments']

            ini = bt.request.forms['ini']
            stop_after = bt.request.forms['stop_after']
            if stop_after:
                stop_after = int(stop_after)
            repeat = 'repeat' in bt.request.forms
            delete_data = 'delete_data' in bt.request.forms

            message = start_run(ini=ini, stop_after=stop_after, comments=comments, repeat=repeat,
                                delete_data=delete_data)

    else:
        message = "Invalid action %s" % action

    return bt.template(message_page, message=message)


if __name__ == '__main__':
    main()