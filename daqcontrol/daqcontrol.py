from collections import OrderedDict
import random
import datetime
import time
import threading
import ptyprocess
from queue import Queue, Empty

import bottle as bt

kodiaq_command_queue = Queue()
kodiaq_running = False
kodiaq_taking_data = False
timed_actions = []      # list of threading.Timer() objects that are waiting

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

Comments for new run:<br/>
<textarea name="comments" cols="40" rows="5" {{run_form_status}}>
{{default_comment}}
</textarea>
<br/>

<br/><br/><br/>

<h2>List of runs:</h2></br>
<table>
<tr> <td>Name</td> <td>Ini</td> <td>Start</td> <td>Duration (min)</td>  <td>Events</td> <td>Comments</td> </tr>
% for r in rundocs:
<tr>
    <td>{{r.get('name')}}</td>
    <td>{{r.get('ini')}}</td>
    <td>someday</td>
    <td>not too long</td>
    <td>many</td>
    <td>{{r.get('comments')}}</td>
</tr>
% end
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
                print("Kodiaq not (yet) alive")
                time.sleep(1)
                continue
            try:
                print(kodiaq.read(10), end="")
            except EOFError:
                # Kodiaq is about to quit
                print("Got EOF when reading kodiaq's output, probably you're shutting down kodiaq?")
                break

    while True:
        try:
            message = q.get_nowait()

        except Empty:
            time.sleep(1)
            continue

        if kodiaq is None:
            if message == 'start':
                print("Starting kodiaq")
                kodiaq = ptyprocess.PtyProcessUnicode.spawn(['./koSlave_fake.py'], echo=True)
                threading.Thread(target=slurper, args=(kodiaq,)).start()
            else:
                raise ValueError("Invalid message %s while kodiaq not running" % message)

        else:
            print("Sending keystroke >%s< to kodiaq" % message)
            kodiaq.write(message)

            if message == 'q':
                kodiaq.wait()
                kodiaq = None


def start_run(ini='', stop_after=0, comments='', repeat=False):
    global kodiaq_taking_data, timed_actions

    #TODO: Insert collection name and comments in ini, pass ini to kodiaq

    kodiaq_command_queue.put('s')
    kodiaq_taking_data = True

    if stop_after:
        print("Scheduling run stop after %d seconds" % stop_after)
        t = threading.Timer(stop_after, stop_run)
        t.start()
        timed_actions.append(t)
    if repeat:
        restart_after = stop_after + 10
        print("Scheduling run restart after %d seconds" % restart_after)

        # Start the run 10 seconds after we stop
        t = threading.Timer(restart_after,
                            start_run,
                            kwargs=dict(ini=ini, stop_after=stop_after, comments=comments, repeat=repeat))
        t.start()
        timed_actions.append(t)

    message = "Started run with ini %s, stop_after %s, comments %s, repeat %s" % (ini, stop_after, comments, repeat)
    return message


def stop_run():
    global kodiaq_taking_data
    print("Stopping run")
    kodiaq_command_queue.put('p')
    kodiaq_taking_data = False


def pax_manager():
    while True:
        time.sleep(1)


@bt.route('/')
def view_page():

    # TODO: get collections from MongoDB
    rundocs = [dict(name='example', ini='bla.ini', comments='YAHOO!!')]

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
                       ininames=['bla.ini', 'otherbla.ini'],
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

            message = start_run(ini=ini, stop_after=stop_after, comments=comments, repeat=repeat)

    else:
        message = "Invalid action %s" % action

    return bt.template(message_page, message=message)


if __name__ == '__main__':
    main()