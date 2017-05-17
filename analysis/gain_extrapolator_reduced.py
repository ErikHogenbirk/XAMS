import numpy as np


setfits = {'170201PMT1': {'a': 21.580428182131726,
  'aerr': 0.52889540892422737,
  'd': 52.477129679468284,
  'derr': 1.2481502872793866},
 '170201PMT2': {'a': 15.938091117290694,
  'aerr': 0.27938061439879242,
  'd': 48.253258795950572,
  'derr': 1.5683314481684414},
 '170313PMT1': {'a': 19.005679895558796,
  'aerr': 0.389806357235009,
  'd': 54.461222131994887,
  'derr': 2.2487908687898255},
 '170313PMT2': {'a': 9.6754895623321318,
  'aerr': 0.088314332839852155,
  'd': 47.742894914431162,
  'derr': 0.67560628377018328}}

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
