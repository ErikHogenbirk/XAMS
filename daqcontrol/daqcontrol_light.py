"""
DAQControl program for XAMS DAQ.
This program facilitates running Kodiaq () via webbrower-style interface
Reads configuration files from a folder.
Main program build by Jelle Aalbers, later modifications by Erik Hogenbirk
Modified to light version that does not run pax (strax-based analysis).
"""


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
from prettytable import PrettyTable

from pax import core

prefab_ini_folder = 'ini'
kodiaq_location = '/home/xams/kodiaq/src/slave'

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
Repeat <input type='text' name='repeat_n' size=5 {{run_form_status}}/> times (0 = repeat forever).<br/>
Delete data from Mongo after reading <input type='checkbox' name='delete_data' checked {{run_form_status}}/><br/>
Do not autoprocess <input type='checkbox' name='do_not_process' {{run_form_status}}/><br/>


Comments for new run:<br/>
<textarea name="comments" cols="40" rows="5" {{run_form_status}}>
{{default_comment}}
</textarea>
<br/>

<br/><br/><br/>

<h2>List of runs:</h2></br>
<table>
<tr> <td>Name</td> <td>Ini</td> <td>Start (UTC)</td> <td>Duration (min)</td>  <td>Events</td> <td>Comments</td> <td>Location</td> <td>Processing status</td> </tr>
% for r in rundocs:
<tr>
    <td>{{r['ini']['mongo']['collection']}}</td>
    <td>{{r['ini'].get('ini_template_name', '')}}</td>
    <td>{{r['start'].strftime('%Y/%m/%d %H:%M:%S')}}</td>
    <td>{{'%0.1f' % ((r['end'] - r['start']).total_seconds() / 60) if 'end' in r else 'Still running'}}</td>
    <td>{{r.get('events_built', '?')}}</td>
    <td>{{r['ini'].get('comments', '')}}</td>
    <td>{{r['ini'].get('data_folder', '?')}}</td>
    <td>{{r.get('processing_status', '?')}}</td>

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

    tag_thread = threading.Thread(target=tag_manager)
    tag_thread.start()

    # host 0.0.0.0 allows for access from other PCs in the Nikhef network
    bt.run(host='0.0.0.0', port=8080)


def kodiaq_manager(q):
    """Thread that babysits kodiaq (main thread is listening for HTTP requests)
    q: queue to receives messages. Message is either 'start', which triggers starting kodiaq, or any string which will
    be passed to kodiaq verbatim.
    """
    kodiaq = None

    # I don't see how we can do STDOUT redirection with ptyprocess
    # read is blocking, so we need a slurper thread:
    def slurper(kodiaq):
        time.sleep(1)
        while True:
            if kodiaq is None or not kodiaq.isalive():
                print("[kodiaqslurper] Kodiaq died?? ending slurper thread.")
                break
            try:
                # Get some bytes from kodiaq. This is a blocking call: if kodiaq does not exit but stops producing
                # output it could never complete
                print(kodiaq.read(10), end="")
            except EOFError:
                # Kodiaq is about to quit
                print("[kodiaqslurper] kodiaq sent EOF. Probably its' saying goodbye because you're shutting it down.")
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
                time.sleep(1)
                # This forces kodiaq to quit (even sending SIGKILL if necessary)
                # To ensure we never have two kodiaqs running
                kodiaq.close()
                print("[kodiaqmanager] Kodiaq has been terminated")
                kodiaq = None


def start_run(ini, stop_after=0, repeat_n=0, comments='', delete_data=True, do_not_process=False):
    global kodiaq_taking_data, timed_actions

    #TODO: Insert collection name and comments in ini, pass ini to kodiaq
    with open(os.path.join(prefab_ini_folder, ini), mode='r') as data_file:
        ini_data = json.load(data_file)

    ini_data['mongo']['collection'] = datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S')
    ini_data['comments'] = comments
    ini_data['ini_template_name'] = ini[:-4]
    ini_data['delete_data'] = delete_data
    ini_data['do_not_process'] = do_not_process

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
    if repeat_n:
        restart_after = stop_after + 10 + extra_delay
        print("[daqcontrol] Still got %d runs left to do so" % repeat_n)
        print("[daqcontrol] Scheduling run restart after %d seconds" % restart_after)
        repeat_n = repeat_n -1

        # Start the run 10 seconds after we stop
        t = threading.Timer(restart_after,
                            start_run,
                            kwargs=dict(ini=ini, stop_after=stop_after, comments=comments, repeat_n=repeat_n, delete_data = delete_data, do_not_process = do_not_process))
        t.start()
        timed_actions.append(t)

    message = "[daqcontrol] Started run with ini %s, stop_after %s, comments %s, repeat_n %s" % (ini, stop_after, comments, repeat_n)
    return message


def stop_run():
    global kodiaq_taking_data
    print("[daqcontrol] Stopping run")
    kodiaq_command_queue.put('p')
    kodiaq_taking_data = False


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

    # Sort ini names alphabetically and case-insensitive, and put default on top
    ininames = sorted([x for x in os.listdir(prefab_ini_folder) if x.endswith('.ini')],
                      key = lambda s: s.lower())
    ininames.insert(0, ininames.pop(ininames.index('default.ini')))

    return bt.template(the_page,
                       rundocs=rundocs,
                       message=bt.request.query.message,
                       default_comment=default_comment,
                       run_form_status='' if can_start_run else 'disabled',
                       ininames=ininames,
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
            repeat_n = bt.request.forms['repeat_n']
            if repeat_n:
                repeat_n = int(repeat_n)
            delete_data = 'delete_data' in bt.request.forms
            do_not_process = 'do_not_process' in bt.request.forms


            message = start_run(ini=ini, stop_after=stop_after, repeat_n = repeat_n, comments=comments,
                                delete_data=delete_data, do_not_process=do_not_process)

    else:
        message = "Invalid action %s" % action

    return bt.template(message_page, message=message)


def tag_manager():
    while True:
        # Check if there are runs that do not have a processing status yet
        runs_todo = list(runs_collection.find({'processing_status': {'$exists': False}}))
        # We assume they are taking data currently (should only be one, actually, so something went wrong if there are more. Add warning?)
        for run_doc in runs_todo:
            run_name = run_doc['name']
            print('[tag_updater] setting tag of run %s to taking data' % run_name)
            runs_collection.find_one_and_update({'name': run_name},
                                                    {'$set': {'processing_status': 'taking_data'}})

        # Check if there is a run that just finished
        runs_todo = list(runs_collection.find({'processing_status': 'taking_data', 'end': {'$exists' : True}}))
        for run_doc in runs_todo:
            run_name = run_doc['name']
            print('[tag_updater] setting tag of run %s to pending' % run_name)
            runs_collection.find_one_and_update({'name': run_name},
                                                    {'$set': {'processing_status': 'pending'}})

        if not runs_todo:
            # print("[tag_updater] No more runs to process, waiting a while...")
            time.sleep(1)
            continue




if __name__ == '__main__':
    main()
