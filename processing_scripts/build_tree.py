import hax
import os
import sys

args = sys.argv

processed_data_path = args[1]
run_name = args[2]
minitree_path = '/data/xenon/xams/run8/minitrees/'

print('Will look for run %s in path %s' % (run_name, processed_data_path))

hax.init(
    experiment='XAMS', 
    pax_version_policy='loose', use_runs_db = False,
    main_data_paths = [processed_data_path],
    minitree_paths = [minitree_path]
         )
         
d = hax.minitrees.load(run_name, ['Fundamentals', 'Basics'])

print('Done!')
