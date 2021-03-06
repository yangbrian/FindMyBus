import re
import json

class Stop:
    def __init__(self,name,code, buses, direction):
        self.name = name
        self.audioName = self.convertAudioName(name)
        self.code = code
        self.buses = buses
        self.audioName += " " + self.convertAudioDirection(direction)
    def __repr__(self):
        return json.dumps(self.__dict__)


    # def __repr__(self):
    #     ret = self.name+"\n"
    #     for bus in self.buses:
    #         ret += "\t--"+bus+"\n"
    #     return ret

    def convertAudioName(self, name):
        with_space = {
            'W' : 'West',
            'E' : 'East',
            'BL' : 'BLVD',
            '&' : 'AND',
            '/' : ' AND ',
            'PL': 'PLACE',
            'PY' : 'PARKWAY',
            'DR' : 'DRIVE',
            'ST' : 'STREET'
            }
        no_space = {
            "/" : " AND "
        }
        for k in with_space:
            my_regex = r"\b" + re.escape(k) + r"\b"
            name = re.sub(my_regex, with_space[k], name)
        for k in no_space:
            name = name.replace('/', ' AND ')
        return name
    
    def convertAudioDirection(self, direction):
        expansions = {
            'N' : 'North',
            'S' : 'South',
            'W' : 'West',
            'E' : 'East'
        }

        output = ''

        for char in direction:
            output += expansions[char]

        return output + ' bound'
