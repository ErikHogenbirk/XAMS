import os
import time
import numpy as np

version = '2' # (May 22, 2017)

# Debug options
debug = False
submit_just_one = True

print('Starting reprocessing version %s...' % version)
if debug:
	print("Warning: debug mode enabled, will NOT submit jobs...")


# settings
nap_time = 10 # Seconds
# cpus = 4

def get_run_list(path, start_at=None, stop_at=None):
    '''
    Get a list of all runs between two datasets (inclusive) in a folder.
    '''
    file_list = np.sort(os.listdir(path))
    
    if start_at:
        start_index = np.where(np.array(file_list) == start_at)[0][0]
        file_list = file_list[start_index:]
    if stop_at:
        stop_index = np.where(np.array(file_list) == stop_at)[0][0]
        file_list = file_list[:stop_index+1]
    print('Run list contains %d files' % len(file_list))
    return file_list

script_template = """#!/bin/bash
export PATH=/data/xenon/xams/anaconda3/bin:$PATH
source activate pax
echo paxer --input {input_path} --output {output_path} --config_path {config_path}  
paxer --input {input_path} --output {output_path} --config_path {config_path}
"""
    
# To do list is a list of dictionaries containing the files to process
to_do_list = [
        {
        # AmBe first standard conditions
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900.ini',
        'first_file' : '170321_155957',
        'last_file' : '170322_081037'
        },
        {
        # AmBe second standard conditions
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900.ini',
        'first_file' : '170322_154130',
        'last_file' : '170322_233141'
        },
        {
        # AmBe conditions Cs
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900.ini',
        'first_file' : '170323_144804',
        'last_file' : '170323_151843'
        },
        {
        # AmBe conditions BG
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900.ini',
        'first_file' : '170323_175029',
        'last_file' : '170324_072500'
        },
    
        ]


for cf in to_do_list:
    # 'long run'  is a set of multiple datasets... 
    dataset_list = get_run_list(cf['raw_path'], cf['first_file'], cf['last_file'])
    

    
    for dataset in dataset_list:
        script_name = ('p_%s.sh' % dataset)
        script_file = open(script_name, 'w')
        script_file_content = script_template.format(
            input_path   = os.path.join(cf['raw_path'], dataset),
            output_path  = os.path.join(cf['processed_path'], dataset),
            config_path = cf['config_path']
        )

        script_file.write(script_file_content)
        script_file.close()

        # Are you sure...?
        if not debug:
            os.system('qsub %s' % script_name)
        print('Submitted job for run %s...' % dataset)
        time.sleep(2)
        if submit_just_one:
            print('Done, since only submitting one.')
            break



