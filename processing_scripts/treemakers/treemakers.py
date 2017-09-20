

# File produced August 28, 2017


# In[2]:

import hax
import numpy as np

class S1TimeProperties(hax.minitrees.TreeMaker):
    '''
    This replaces the ExtraS1S2Properties which causes some memory problems...
    Added area midpoint in version 0.0.4 (needed for alignment, apparently)
    September 6, 2017, Erik Hogenbirk
    '''
    __version__ = '0.0.4'
    extra_branches  = ['peaks.*', 'interactions*']
    
    def extract_data(self, event):
        peak_properties = ['n_saturated_channels', 'center_time', 'left', 'right', 'area_midpoint']

        # Peak properties for S1 and S2 that are in lists...
        extra_properties = ['time_from_midpoint_10p', 'time_from_midpoint_20p',
                            'time_from_midpoint_30p', 'time_from_midpoint_40p',
                            'range_20p_area', 'range_80p_area'
                           ]
        result_vars = ['s1_' + _pp for _pp in (peak_properties + extra_properties) ]
        result = {k: float('nan') for k in result_vars}
        
        if len(event.interactions) == 0:
            # No interactions? Then no S1.
            return result

        # We have an interaction! Extract the peak index of the S1...
        s1_index = event.interactions[0].s1
        # Extract all standard properties
        for prop in peak_properties:
            result['s1_' + prop] = getattr(event.peaks[s1_index], prop)
        # Here come nonstandard properties
        for i in range(10):
            if ('range_%d0p_area' % i) in extra_properties:
                result['s1_range_%d0p_area' % i] = (
                    list(event.peaks[s1_index].range_area_decile)[i])
            if ('time_from_midpoint_%d0p' % i) in extra_properties:
                result['s1_time_from_midpoint_%d0p' % i] = (
                    list(event.peaks[s1_index].area_decile_from_midpoint)[i])
                
        return result
        



class S1Pulse(hax.minitrees.TreeMaker):
    '''
    Retrieves the S1 waveform. Use pickle as format for this one.
    '''
    __version__ = '0.0.2'
    extra_branches = ['*']
    
    def extract_data(self, event):
        result = {'s1_pulse' : None}
        
        # No interaction means no S1 so skip this event
        if len(event.interactions) == 0:
            return result
        
        s1_index = event.interactions[0].s1
        s1 = event.peaks[s1_index]
        
        result['s1_pulse'] = list(getattr(s1, 'sum_waveform'))[200:400] # New in version 0.0.2: -100 - +300 ns
        return result


# In[ ]:

class XAMSProperties(hax.minitrees.TreeMaker):
    '''
    Get properties for XAMS
    
    '''
    __version__ = '0.1.0'
    
    extra_branches = ['peaks.*', 'peaks.range_area_decile*', 
                      'interactions*']
    
    def extract_data(self, event):
        
        peak_types = ['s1', 's2']
        peak_properties = ['area_fraction_top', 'area', 'center_time', 'n_saturated_channels']
        extra_properties = ['range_50p_area', 'range_70p_area']
        all_properties = peak_properties + extra_properties
        result_vars = [_pt + '_' + _pp for _pt in peak_types for _pp in all_properties ]
        result = {k: float('nan') for k in result_vars}
        
        interaction_properties = ['drift_time']
        for _prop in interaction_properties:
            result[_prop] = float('nan')
            
        s1s = []
        s2s = []
        
        for peak in event.peaks:
            if peak.type == 's1':
                s1s.append(peak)
            if peak.type == 's2':
                s2s.append(peak)
        
        # Reverse-sort by area
        s1s = sorted(s1s, key = lambda peak: - peak.area)
        s2s = sorted(s2s, key = lambda peak: - peak.area)

        
        # Now load properies
        result['n_s1s'] = len(event.s1s)
        result['n_s2s'] = len(event.s2s)
        
        
        for peak_name, peak_list in zip(['s1', 's2'], [s1s, s2s]):
            if len(peak_list) == 0:
                continue
            # First peak in list sorted by area
            peak = peak_list[0]
            for _prop in peak_properties:
                result[peak_name + '_' + _prop] = getattr(peak, _prop)
            for i in range(10):
                if ('range_%d0p_area' % i) in extra_properties:
                    result[peak_name + '_' + 'range_%d0p_area' % i] = list(peak.range_area_decile)[i]
        
        if len(s2s) > 1:
            result['largest_other_s2'] = getattr(s2s[1], 'area')
        else:
            result['largest_other_s2'] = 0.
            
        result['drift_time'] = result['s2_center_time'] - result['s1_center_time']
        



#             for peak_type, peak_index in zip(peak_types, [s1,s2]):
#                 for _prop in peak_properties:
#                     result[peak_name + '_' + _prop] = getattr(event.peaks[peak_index], _prop)

#                 if 'range_50p_area' in extra_properties:
#                     result[peak_name + '_' + 'range_50p_area'] = list(event.peaks[peak_pos].range_area_decile)[5]
        
        return result


# In[ ]:

class NaIProperties(hax.minitrees.TreeMaker):
    '''
    Add the properties that are closest to the TPC interaction.
    Proximity based on a small delay (since pulse comes a bit later)
    '''
    __version__ = '0.1.3'
    extra_branches = ['peaks.*', 'interactions*']
    s1_offset = 16. # ns from left edge
    
    def extract_data(self, event):
        ret = {
            'NaI_area' : float('nan'),
            'NaI_time_from_s1': float('nan'),
            'NaI_time_from_s1_corr': float('nan'),
            'NaI_left' : float('nan'),
            'NaI_n_peaks' : 0,
              }
        # Check if the interaction exists
        if len(event.interactions) == 0:
            return ret
        
        main_s1_index = event.interactions[0].s1
        s1_left = getattr(event.peaks[main_s1_index], 'left')        
        
        time_from_s1 = []
        time_from_s1_corr = []
        area = []
        left = []
        
        for p in event.peaks:
            if getattr(p, 'detector') == 'nai':
                time_from_s1.append((getattr(p, 'left') - s1_left) * 2.)
                time_from_s1_corr.append((getattr(p, 'left') - s1_left) * 2. - self.s1_offset)
                area.append(getattr(p, 'area'))
                left.append(getattr(p, 'left'))
        
        if len(area) == 0:
            return ret
        
        index_of_closest_peak = np.argmin(abs(np.array(time_from_s1_corr)))
        ret['NaI_area'] = area[index_of_closest_peak]
        ret['NaI_left'] = left[index_of_closest_peak]
        ret['NaI_time_from_s1'] = time_from_s1[index_of_closest_peak]
        ret['NaI_time_from_s1_corr'] = time_from_s1_corr[index_of_closest_peak]
        ret['NaI_n_peaks'] = len(area)
        return ret

