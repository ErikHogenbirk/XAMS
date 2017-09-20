import os
import time
import pymongo

version = '0.0.3' # (Feb. 6, 2017)
print('Starting autoprocess version %s...' % version)

# settings
nap_time = 10 # Seconds
# cpus = 4

script_template = """#!/bin/bash
export PATH=/data/xenon/xams/anaconda3/bin:$PATH
source activate pax
echo paxer --input {input_path} --output {output_path} --config_path {config_path}  
paxer --input {input_path} --output {output_path} --config_path {config_path}
touch /data/xenon/xams/auto_processing/pax_done/{run_name}
"""
    

# connect to database
# client = pymongo.MongoClient('145.102.135.93')
# Use this one (localhost) if you have an ssh port forwarded
client = pymongo.MongoClient()

runs_db = client['run']
runs = runs_db['runs']

while 1:
    # Update task list
    run_docs_to_do = list(runs.find({'event_building_complete' : True, 'processing_status' : 'pending'}))
    # run_docs_to_do = list(runs.find({'name' : '170202_124836'}))

    if len(run_docs_to_do) > 0:
        print('I found %d runs to process, time to get to work!' % len(run_docs_to_do))
        print('These runs I will do:')
        for run_doc in run_docs_to_do:
            print(run_doc['name'])
    
    for run_doc in run_docs_to_do:
        run_doc['lena_raw_data_folder'] = run_doc['ini']['data_folder'].replace('/home/xams/lena', '/data/xenon/xams')
        run_doc['lena_processed_data_folder'] = run_doc['lena_raw_data_folder'].replace('raw', 'processed')
        
        script_name = ('p_%s.sh' % run_doc['name'])
        script_file = open(script_name, 'w')
        script_file_content = script_template.format(
            input_path   = os.path.join(run_doc['lena_raw_data_folder'], run_doc['name']),
            output_path  = os.path.join(run_doc['lena_processed_data_folder'], run_doc['name']),
            run_name = run_doc['name'],
         #                                    cpus = cpus,
                                             config_path = run_doc['ini']['lena_pax_config_path']


        )

        script_file.write(script_file_content)
        script_file.close()
        
        runs.find_one_and_update({'name': run_doc['name']},
                                                {'$set': {
                    'processing_status': 'processing',
                    'lena_raw_data_folder' : run_doc['lena_raw_data_folder'],
                    'lena_processed_data_folder' : run_doc['lena_processed_data_folder']
                                                         }})
        # Are you sure...?
        os.system('qsub %s' % script_name)
        print('Submitted job for run %s...' % run_doc['name'])
        time.sleep(2)




    print("Waiting %d seconds before rechecking for unprocessed runs..."% nap_time)
    time.sleep(nap_time)

