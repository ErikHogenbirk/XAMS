import hax
import os
import sys
import numpy as np
from treemakers import S1TimeProperties
debug = False

args = sys.argv
processed_data_path = args[1]
run_name = args[2]
minitree_path = '/data/xenon/xams/run8/minitrees/'

hax.init(
    experiment='XAMS', 
    pax_version_policy='loose', use_runs_db = False,
    main_data_paths = [processed_data_path],
    minitree_paths = [minitree_path],
         )

if not debug:
    d = hax.minitrees.load(run_name, ['Fundamentals', 'Basics', S1TimeProperties])
print('Done!')
