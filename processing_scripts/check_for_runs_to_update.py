import os
import time
import pymongo

version = '0.0.1'
print('Starting updater, version %s' % version)

time_to_sleep = 60 # seconds. Not too short, get file conflict errors!

client = pymongo.MongoClient()
runs_db = client['run']
runs = runs_db['runs']

print('Connected!')



while 1:
    # Check if pax is done
    update = os.listdir('pax_done')
    
    if len(update) > 0:
        print('Something to update, because pax is done! Here we go!')
        print('Will update these datasets:')
        for run_name in update:
            print(run_name)
    
    for run_name in update:
        runs.find_one_and_update({'name': run_name},
                                 {'$set': {'processing_status': 'pending_minitrees'}})
        print('Status updated for run %s' % run_name)
        os.system('rm ./pax_done/%s' % run_name)
    
    # Check if pax is done
    update = os.listdir('hax_done')
    
    if len(update) > 0:
        print('Something to update, because hax is done! Here we go!')
        print('Will update these datasets:')
        for run_name in update:
            print(run_name)
    
    for run_name in update:
        runs.find_one_and_update({'name': run_name},
                                 {'$set': {'processing_status': 'done'}})
        print('Status updated for run %s' % run_name)
        os.system('rm ./hax_done/%s' % run_name)


    print('Will now sleep for %d seconds...' % time_to_sleep)
    time.sleep(time_to_sleep)
