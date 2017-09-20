
# coding: utf-8

# In[ ]:

import sys
import pymongo

run_name = sys.argv[1]

print('Will update status for run %s' % run_name)

# client = pymongo.MongoClient('145.102.135.93')
# Use this one (localhost) if you have an ssh port forwarded
client = pymongo.MongoClient()

runs_db = client['run']
runs = runs_db['runs']


runs.find_one_and_update({'name': run_name},
                                        {'$set': {
            'processing_status': 'done'}})
print('Status updated!')

