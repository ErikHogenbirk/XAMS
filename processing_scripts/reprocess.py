################################ SETTINGS

# Debug options
debug = False
submit_just_one = False
force_start = False

nap_time = 30 # Seconds
processing_base_path = '/data/xenon/xams/auto_processing/processing_dir/'
mode = 'minitrees_basics' # Choose 'process', 'minitrees_basics', 'minitrees_basics_na22' or 'minitrees_s1pulse'
if debug: nap_time = 1

################################ MAIN PROGRAM
import os
import time
import sys
import numpy as np

version = '3.1.1' # (August, 30, 2017)

print('Starting reprocessing version %s...' % version)
print('The mode is %s.' % mode)
if debug:
	print("Warning: debug mode enabled, will NOT submit jobs...")
else:
    if not force_start:
        amsure = input('Are you sure you want to submit jobs? (y/n) ')
        if not amsure == 'y':
            print('Then we will quit, goodbye!')
            sys.exit(0)
    else:
        print('Force start enabled, here we go!')

# Auxilary functions
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

if mode == 'process':
    script_template = """#!/bin/bash
export PATH=/data/xenon/xams/anaconda3/bin:$PATH
source activate pax
mkdir {processing_path}
cd {processing_path}
rm pax_event_class*
echo paxer --input {input_path} --output {dataset_name} --config_path {config_path}  
paxer --input {input_path} --output {dataset_name} --config_path {config_path}
echo 'Pax is done, moving data...'
mv {dataset_name}.root {output_path}.root
echo 'Done!'
"""
elif mode == 'minitrees_s1pulse':
    script_template = """#!/bin/bash
export PATH=/data/xenon/xams/anaconda3/bin:$PATH
source activate pax
mkdir {processing_path}
cd {processing_path}
rm pax_event_class*
python /data/xenon/xams/auto_processing/treemakers/build_S1Pulse.py {processed_path} {dataset_name}
echo 'Done!'
"""
elif mode == 'minitrees_basics':
    script_template = """#!/bin/bash
export PATH=/data/xenon/xams/anaconda3/bin:$PATH
source activate pax
mkdir {processing_path}
cd {processing_path}
rm pax_event_class*
python /data/xenon/xams/auto_processing/treemakers/build_Basics.py {processed_path} {dataset_name}
echo 'Done!'
"""
elif mode == 'minitrees_basics_na22':
    script_template = """#!/bin/bash
export PATH=/data/xenon/xams/anaconda3/bin:$PATH
source activate pax
mkdir {processing_path}
cd {processing_path}
rm pax_event_class*
python /data/xenon/xams/auto_processing/treemakers/build_Basics_Na22.py {processed_path} {dataset_name}
echo 'Done!'
"""
else:
    raise NotImplementedError('Mode does not exist, you gave %s, use process, minitrees_s1pulse, '+
    'minitrees_basics or minitrees_basics_na22!' % mode)
    
# To do list is a list of dictionaries containing the files to process
to_do_list = [
        ############################# ZERO CATHODE FIELD DATA
        {
        # AmBe zero field 
        'raw_path' : '/data/xenon/xams/run8/raw/s1_only/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_900_950_medium.ini',
        'first_file' : '170324_161817',
        'last_file' : '170324_215007',
        # 170327_070907 last file
		'process_me' : False
        },
        {
        # Cs zero field, stable settings
        'raw_path' : '/data/xenon/xams/run8/raw/s1_only/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_900_950_medium.ini',
        'first_file' : '170327_080108',
        'last_file' : '170327_095258',
		'process_me' : False
        },
        {
        # Cs zero field, Nonstable settings
        'raw_path' : '/data/xenon/xams/run8/raw/s1_only/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_900_950_medium.ini',
        'first_file' : '170327_073915',
        'last_file' : '170327_075317',
		'process_me' : False
        },
        ############################# LOW CATHODE FIELD DATA
        {
        # AmBe lowfield 
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_medium.ini',
        'first_file' : '170324_093626',
        'last_file' : '170324_124119',
		'process_me' : True
        },
        {
        # Cs lowfield 
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_medium.ini',
        'first_file' : '170324_130241',
        'last_file' : '170324_144835',
		'process_me' : True
        },
        ############################# HIGH CATHODE FIELD DATA
        {
        # AmBe first standard conditions (AmBe 1)
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_medium.ini',
        'first_file' : '170321_155957',
        'last_file' : '170321_214847', # 6 hours of data
#        'last_file' : '170322_081037',
		'process_me' : True
        },
        {
        # AmBe second standard conditions (AmBe 2)
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_medium.ini',
        'first_file' : '170322_154130',
        'last_file' : '170322_213020', # 6 hours of data       
#        'last_file' : '170322_233141',
		'process_me' : True
        },
        {
        # AmBe conditions Cs
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_medium.ini',
        'first_file' : '170323_144804',
        'last_file' : '170323_151843',
		'process_me' : True
        },
        {
        # AmBe conditions BG
        'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_medium.ini',
        'first_file' : '170323_175029',
        'last_file' : '170323_232220',
#        'last_file' : '170324_072500',
		'process_me' : True
        },
        {
        # AmBe conditions Na (Na22_1) (DAQ errors in here)
        'raw_path' : '/data/xenon/xams/run8/raw/Na22/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_Na22_medium.ini',
        'first_file' : '170323_121631',
        'last_file' : '170323_134830',
		'process_me' : True
        },
        {
        # AmBe conditions Na (Na22_2)
        'raw_path' : '/data/xenon/xams/run8/raw/Na22/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2_medium/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_850_900_Na22_medium.ini',
        'first_file' : '170323_140425',
        'last_file' : '170323_142831',
		'process_me' : True
        },
        ############################# PHOTOPEAK CALIBRATION DATA
		{
		# Na-22 calibration
		'raw_path' : '/data/xenon/xams/run8/raw/Na22',
        'processed_path' : '/data/xenon/xams/run8/processed_v2/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_700_750_Na22.ini',
        'first_file' : '170323_155714',
		'last_file' : '170323_161452',
		'process_me' : False
		},
		{
		# Cs-137 calibration
		'raw_path' : '/data/xenon/xams/run8/raw/data/',
        'processed_path' : '/data/xenon/xams/run8/processed_v2/',
        'config_path' : '/data/xenon/xams/run8/pax_ini/v2/XAMS_700_750.ini',
        'first_file' : '170323_152801',
		'last_file' : '170323_154257',
		'process_me' : False
		},
		
        ]


for cf in to_do_list:
    # 'long run'  is a set of multiple datasets... 
    if not cf['process_me']:
        continue

    dataset_list = get_run_list(cf['raw_path'], cf['first_file'], cf['last_file'])
    print(dataset_list)
    for dataset in dataset_list:
        # Make different script files for processing or minitree building
        script_name = ('scripts/p_%s_%s.sh' % (dataset, mode))
        script_file = open(script_name, 'w')
        script_file_content = script_template.format(
            input_path   = os.path.join(cf['raw_path'], dataset),
			output_path  = os.path.join(cf['processed_path'], dataset),
            processed_path = cf['processed_path'],
            config_path = cf['config_path'],
			processing_path = os.path.join(processing_base_path, '%s_%s' % (dataset, mode)),
			dataset_name = dataset
        )

        script_file.write(script_file_content)
        script_file.close()

        # Are you sure...?
        if not debug:
            os.system('qsub %s' % script_name)
        print('Submitted job for run %s...' % dataset)
        time.sleep(nap_time)
        if submit_just_one:
            print('Done, since only submitting one.')
            break



