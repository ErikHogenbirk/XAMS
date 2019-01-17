import numpy as np

# Values from mail Kiefer 17/5/2017
setfits = {'170201PMT1': {'a': 21.224314613249888,
  'aerr': 0.4030051437440344,
  'd': 53.108714558044085,
  'derr': 1.0821335352911126},
 '170201PMT2': {'a': 15.74889181593406,
  'aerr': 0.25679834384355804,
  'd': 47.554300980649138,
  'derr': 1.5505761322476683},
 '170313PMT1': {'a': 19.022565970971623,
  'aerr': 0.34618678311692352,
  'd': 51.971637725790139,
  'derr': 1.1097431799787225},
 '170313PMT2': {'a': 9.7919666086832748,
  'aerr': 0.13758541647647685,
  'd': 47.917798733190516,
  'derr': 0.47316378534303566}}

def gainexp(x, a, d):
        return a*2**((x-1000)/d)
    
def gainexperr(x, a, aerr, d, derr):
        return 2**((x-1000)/d)*np.sqrt((a*np.log(2)*(x-1000)*d**(-2)*derr)**2 + aerr**2)

def gainextrapolator(set_name = '', voltage = ''):
        a    = setfits[set_name]['a']
        aerr = setfits[set_name]['aerr']
        d    = setfits[set_name]['d']
        derr = setfits[set_name]['derr']
        x = voltage
        gain = gainexp(x, a, d)
        gainerr = gainexperr(x, a, aerr, d, derr)
        # print("Extrapolated gain is " + str(round(gain, 3)) + " +-" + str(round(gainerr, 3)))
        return gain

def get_gain(pmt_number, voltage):
    set_name = '170313PMT%d' % pmt_number
    return gainextrapolator(set_name=set_name, voltage=voltage) * 1e6
