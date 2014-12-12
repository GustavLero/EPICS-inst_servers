from pcaspy import SimpleServer, Driver, cas
import re


class DynamicStringPV(cas.casPV):
    def __init__(self, data):
        cas.casPV.__init__(self)
        self.stored_value = cas.gdd()
        self.stored_value.setPrimType(cas.aitEnumUint8)
        self.stored_value.put(data)

    def getValue(self, value):
        if value.primitiveType() == cas.aitEnumInvalid:
            value.setPrimType(cas.aitEnumUint8)
        value.put(self.stored_value.get())
        return cas.S_casApp_success

    def updateValue(self, value):
        self.stored_value.put(value)
        self.stored_value.setTimeStamp()
        self.postEvent(self.stored_value)

    def maxDimension(self):
        return 1

    def maxBound(self, dims):
        return 16000

    def bestExternalType(self):
        return cas.aitEnumUint8

class CAServer(SimpleServer):

    def __init__(self, pv_prefix):
        SimpleServer.__init__(self)

        self._pvs = dict()
        self._prefix = pv_prefix

    def _strip_prefix(self, fullname):
        pvmatch = re.match(self._prefix + r'(.*)', fullname)
        if pvmatch is not None:
            return pvmatch.group(1)
        else:
            return None

    def pvExistTest(self, context, addr, fullname):
        try:
            pv = self._strip_prefix(fullname)
            if pv is not None and pv in self._pvs:
                return cas.pverExistsHere
            else:
                return SimpleServer.pvExistTest(self, context, addr, fullname)
        except:
            return cas.pverDoesNotExistHere

    def pvAttach(self, context, fullname):
        pv = self._strip_prefix(fullname)
        if pv is not None and pv in self._pvs:
            return self._pvs[pv]
        else:
            return SimpleServer.pvAttach(self, context, fullname)

    def registerPV(self, name, data = ''):
        if name not in self._pvs:
            self._pvs[name] = DynamicStringPV(data)

    def updatePV(self, name, data):
        if name in self._pvs:
            self._pvs[name].updateValue(data)
        else:
            self.registerPV(name, data)


if __name__ == '__main__':
    #here for testing
    prefix = 'MTEST:'
    pvdb = { 'STATIC' : {} }

    server = CAServer(prefix)
    server.createPV(prefix, pvdb)
    driver = Driver()

    server.registerPV("TEST")
    server.updatePV("TEST", "TEST initialised, this is a really long string designed to test whether the end is cut off if it is over 40 characters")

    i = 0

    while True:
        try:
            server.process(0.1)
            i += 1
            if (i % 100) == 0:
                server.updatePV("TEST", "I is: " + str(i))
        except KeyboardInterrupt:
            break