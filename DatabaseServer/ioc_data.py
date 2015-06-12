import mysql.connector
from threading import RLock
from server_common.utilities import print_and_log
from mysql_abstraction_layer import SQLAbstraction


class IOCData(object):
    """A wrapper to connect to the IOC database via MySQL"""

    def __init__(self, dbid, procserver, prefix):
        """Constructor

        Args:
            dbid (string) : The id of the database that holds IOC information
            procserver (ProcServWrapper) : An instance of ProcServWrapper, used to start and stop IOCs
            prefix (string) : The pv prefix of the instrument the server is being run on
        """

        # Set up the database connection
        self._db = SQLAbstraction(dbid, dbid, "$" + dbid)

        self._procserve = procserver
        self._prefix = prefix
        self._running_iocs = list()
        self._running_iocs_lock = RLock()

    def check_db_okay(self):
        """Attempts to connect to the database and raises an error if not able
        """
        self._db.check_db_okay()

    def get_iocs(self):
        """Gets a list of all the IOCs in the database and whether or not they are running

        Returns:
            dict : IOCs and their running status
        """
        try:
            sqlquery = "SELECT iocname FROM iocs"
            iocs = dict((element[0], dict()) for element in self._db.execute_query(sqlquery))
        except Exception as err:
            print_and_log("could not get IOCS from database: %s" % err, "MAJOR", "DBSVR")
            iocs = dict()
        for ioc in iocs.keys():
            ioc = ioc.encode('ascii', 'replace')
            with self._running_iocs_lock:
                # Create a copy so we don't lock the list for longer than necessary (do we need to do this?)
                running = list(self._running_iocs)
            if ioc in running:
                iocs[ioc]["running"] = True
            else:
                iocs[ioc]["running"] = False
        return iocs

    def get_active_iocs(self):
        """Gets a list of all the running IOCs

        Returns:
            list : The names of running IOCs
        """
        return self._running_iocs

    def get_sample_pars(self):
        """Gets the sample parameters from the IOC database

        Returns:
            list : A list of the names of PVs associated with sample parameters
        """
        values = []
        try:
            sqlquery = ("SELECT pvname FROM pvs"
                        " WHERE (pvname LIKE '%PARS:SAMPLE:%' AND pvname NOT LIKE '%:SEND'"
                        " AND pvname NOT LIKE '%:SP' AND pvname NOT LIKE '%:TYPE')"
                        )
            # Get as a plain list
            values = [str(element[0]) for element in self._db.execute_query(sqlquery)]
        except Exception as err:
            print_and_log("could not get sample parameters from database: %s" % err, "MAJOR", "DBSVR")
        return values

    def get_beamline_pars(self):
        """Gets the beamline parameters from the IOC database

        Returns:
            list : A list of the names of PVs associated with beamline parameters
        """
        values = []
        try:
            sqlquery = ("SELECT pvname FROM pvs"
                        " WHERE (pvname LIKE '%PARS:BL:%' AND pvname NOT LIKE '%:SEND'"
                        " AND pvname NOT LIKE '%:SP' AND pvname NOT LIKE '%:TYPE')"
                        )
            # Get as a plain list
            values = [str(element[0]) for element in self._db.execute_query(sqlquery)]
        except Exception as err:
            print_and_log("could not get beamline parameters from database: %s" % err, "MAJOR", "DBSVR")
        return values

    def update_iocs_status(self):
        """Accesses the db to get a list of IOCs and checks to see if they are currently running

        Returns:
            list : The names of running IOCs
        """
        with self._running_iocs_lock:
            self._running_iocs = list()
            try:
                # Get all the iocnames and whether they are running, but ignore IOCs associated with PSCTRL
                sqlquery = "SELECT iocname, running FROM iocrt WHERE (iocname NOT LIKE 'PSCTRL_%')"
                rows = self._db.execute_query(sqlquery)
                for row in rows:
                    # Check to see if running using CA and procserv
                    try:
                        if self._procserve.get_ioc_status(self._prefix, row[0]).upper() == "RUNNING":
                            self._running_iocs.append(row[0])
                            if row[1] == 0:
                                # This should only get called if the IOC failed to tell the DB it started
                                self._db.commit("UPDATE iocrt SET running=1 WHERE iocname='%s'" % row[0])
                        else:
                            if row[1] == 1:
                                self._db.commit("UPDATE iocrt SET running=0 WHERE iocname='%s'" % row[0])
                    except Exception as err:
                        # Fail but continue - probably couldn't find procserv for the ioc
                        print_and_log("issue with updating IOC status: %s" % err, "MAJOR", "DBSVR")
            except Exception as err:
                print_and_log("issue with updating IOC statuses: %s" % err, "MAJOR", "DBSVR")

            return self._running_iocs

    def get_interesting_pvs(self, level="", ioc=None):
        """Queries the database for PVs based on their interest level and their IOC.

        Args:
            level (string, optional) : The interest level to search for, either High or Medium. Default to all interest
                                    levels
            ioc (string, optional) : The IOC to search. Default is all IOCs.

        Returns:
            list : A list of the PVs that match the search given by level and ioc

        """
        values = []
        sqlquery = "SELECT pvinfo.pvname, pvs.record_type, pvs.record_desc, pvs.iocname FROM pvinfo"
        sqlquery += " INNER JOIN pvs ON pvs.pvname = pvinfo.pvname"
        where_ioc = ''

        if ioc is not None and ioc != "":
            where_ioc = "AND iocname='%s'" % ioc

        try:
            if level.lower().startswith('h'):
                sqlquery += " WHERE (infoname='INTEREST' AND value='HIGH' {0})".format(where_ioc)
            elif level.lower().startswith('m'):
                sqlquery += " WHERE (infoname='INTEREST' AND value='MEDIUM' {0})".format(where_ioc)
            else:
                # Try to get all pvs!
                pass

            # Get as a plain list of lists
            values = [list(element) for element in self._db.execute_query(sqlquery)]
            # Convert any bytearrays
            for i, pv in enumerate(values):
                for j, element in enumerate(pv):
                    if type(element) == bytearray:
                        values[i][j] = element.decode("utf-8")
        except Exception as err:
            print_and_log("issue with getting interesting PVs: %s" % err, "MAJOR", "DBSVR")
        return values

    def get_active_pvs(self):
        """Queries the database for active PVs.

        Returns:
            list : A list of the PVs in running IOCs

        """
        values = []
        sqlquery = "SELECT pvinfo.pvname, pvs.record_type, pvs.record_desc, pvs.iocname FROM pvinfo"
        sqlquery += " INNER JOIN pvs ON pvs.pvname = pvinfo.pvname"
        # Ensure that only active IOCs are considered
        sqlquery += " WHERE (pvs.iocname in (SELECT iocname FROM iocrt WHERE running=1) AND infoname='INTEREST')"

        try:
            # Get as a plain list of lists
            values = [list(element) for element in self._db.execute_query(sqlquery)]
            # Convert any bytearrays
            for i, pv in enumerate(values):
                for j, element in enumerate(pv):
                    if type(element) == bytearray:
                        values[i][j] = element.decode("utf-8")
        except Exception as err:
            print_and_log("issue with getting active PVs: %s" % err, "MAJOR", "DBSVR")

        return values