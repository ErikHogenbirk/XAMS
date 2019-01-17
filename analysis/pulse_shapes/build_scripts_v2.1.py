exec(open("psd_mc_functions.py").read())
# This script is to build instructions for others

p = dict(n_photons = int(2e6), bootstrap_trials = 250, neglect_systematic = False, dset='nr')
base_name = 'highstat_withsys_nr3'
processing_dir = '/data/xenon/ehogenbi/pulsefit/processing/'
pickles_dir = '/data/xenon/ehogenbi/pulsefit/processing_pickles/'

submit = True
submit_just_one = False
nap_time = 10 # s



x = produce_settings_dicts(['t3', 'fs',  't1', 'tts'], 
                           [19,   0.19,  1.0,  1.0], 
                           [23,   0.21,  4.0,  2.5],
                           [0.5,  0.01,  0.5, 0.25],  
                           25, **p)



shell_base = """#!/bin/bash
source activate pax
cd {processing_dir}
python {python_fn}
"""

python_base = """
print("Here we go, processing like mad!")
print("Reading function definitions...")
exec(open("/data/xenon/ehogenbi/pulsefit/psd_mc_functions.py").read())
print("Definitions read.")
print("Starting reading the pickles ({pickle_file})...")
dicts = single_pickle_read("{pickle_file}")
print("Pickle read.")
d0 = deepcopy(dicts[0])
d0 = get_params(d0)
if d0['stored_stat']:
    print("Building stored_stat parameter...")
    stored_stat = real_s1_wv_sigma(**d0)
    print('Done building stat error.')
print('Starting main GOF loop...')
for p in dicts:
    p['chi2'] = gof(**p)
print("Done. %d settings are processed. Dumping pickle..." % (len(dicts)))
single_pickle_dump("{pickle_file}", dicts)
print('Done, goodbye!')
"""

for directory in [processing_dir, pickles_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory)

pickle_fns = dump_settings_pickles(x, pickles_dir, base_name)


shell_fns = []
python_fns = []
for i, fn in enumerate(pickle_fns):
    # Write shell script
    shell_fn = os.path.join(processing_dir, 'process_%s_%03d.sh' % (base_name, i))
    shell_fns.append(shell_fn)
    python_fn = os.path.join(processing_dir, 'process_%s_%03d.py' % (base_name, i))
    python_fns.append(python_fn)
    with open(shell_fn, 'w') as f:
        f.write(shell_base.format(python_fn = python_fn, processing_dir = processing_dir))
    with open(python_fn, 'w') as f:
        f.write(python_base.format(pickle_file = fn))
print("Done producing files!")
print("Will now proceed to submit %d jobs..." % (len(shell_fns)))
if submit:
    for fn in shell_fns:
        os.system("qsub %s" % fn)
        time.sleep(nap_time)
        if submit_just_one:
            break
    


