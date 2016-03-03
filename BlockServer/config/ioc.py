import copy


class IOC(object):
    """ Represents an IOC.

    Attributes:
        name (string): The name of the IOC
        autostart (bool): Whether the IOC should automatically start
        restart (bool): Whether the IOC should automatically restart
        subconfig (string): The component the IOC belongs to
        macros (dict): The IOC's macros
        pvs (dict): The IOC's PVs
        pvsets (dict): The IOC's PV sets
        simlevel (string): The level of simulation
    """
    def __init__(self, name, autostart=True, restart=True, subconfig=None, macros=None, pvs=None, pvsets=None,
                 simlevel=None):
        """ Constructor.

        Args:
            name (string): The name of the IOC
            autostart (bool): Whether the IOC should automatically start
            restart (bool): Whether the IOC should automatically restart
            subconfig (string): The component the IOC belongs to
            macros (dict): The IOC's macros
            pvs (dict): The IOC's PVs
            pvsets (dict): The IOC's PV sets
            simlevel (string): The level of simulation
        """
        self.name = name
        self.autostart = autostart
        self.restart = restart
        self.subconfig = subconfig

        if simlevel is None:
            self.simlevel = "None"
        else:
            self.simlevel = simlevel

        if macros is None:
            self.macros = dict()
        else:
            self.macros = macros

        if pvs is None:
            self.pvs = dict()
        else:
            self.pvs = pvs

        if pvsets is None:
            self.pvsets = dict()
        else:
            self.pvsets = pvsets

    def _dict_to_list(self, in_dict):
        """ Converts into a format better for the GUI to parse, namely a list.

        It's messy but it's what the GUI wants.

        Args:
            in_dict (dict): The dictionary to be converted

        Returns:
            list : The newly created list
        """
        out_list = []
        for k, v in in_dict.iteritems():
            # Take a copy as we do not want to modify the original
            c = copy.deepcopy(v)
            c['name'] = k
            out_list.append(c)
        return out_list

    def __str__(self):
        data = "Name: %s, Subconfig: %s" % (self.name, self.subconfig)
        return data

    def to_dict(self):
        """ Puts the IOC's details into a dictionary.

        Returns:
            dict : The IOC's details
        """
        return {'name': self.name, 'autostart': self.autostart, 'restart': self.restart,
                'simlevel': self.simlevel, 'pvs': self._dict_to_list(self.pvs),
                'pvsets': self._dict_to_list(self.pvsets), 'macros': self._dict_to_list(self.macros),
                'subconfig': self.subconfig}