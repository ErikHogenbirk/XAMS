from pax import plugin


class XAMSClassification(plugin.TransformPlugin):

    def transform_event(self, event):

        for peak in event.peaks:

            if peak.detector != 'tpc':
                print(peak.hits['channel'], peak.left, peak.right, peak.detector)

            # Work only on unknown peaks - not noise, lone_pulse, and big peaks (which are already s1 or s2)
            if peak.type != 'unknown':
                continue

            if peak.range_area_decile[5] < 60:
                peak.type = 's1'
                continue

            elif peak.range_area_decile[5] > 100 and peak.area > 8:
                peak.type = 's2'
                continue

        return event
