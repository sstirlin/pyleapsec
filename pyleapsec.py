"""
Author:  Spencer Stirling
License:  MIT
"""

import datetime as _datetime
import calendar as _calendar
import time as _time
import urllib2 as _urllib2
import ssl as _ssl
if hasattr(_ssl, '_create_unverified_context'):
    _ssl._create_default_https_context = _ssl._create_unverified_context
import os.path as _ospath
import re as _re

__all__ = ['LeapSecondConverter',]


class LeapSecondConverter():

    _leapfile_url = "ftp://maia.usno.navy.mil/ser7/tai-utc.dat"
    _leapfile_prefix = "leap_second_converter_"
    _month_abbr_to_num = {name.upper(): num for num, name in enumerate(_calendar.month_abbr) if num}
    utc_unix_epoch = _datetime.datetime(1970, 1, 1) 
    utc_gps_epoch = _datetime.datetime(1980, 1, 6) 

    def __init__(self, refresh_days=30, cache_dir=''):

        # initialize some variables
        self._refresh_seconds = refresh_days*86400
        self._cache_dir = cache_dir
        if self._cache_dir == '':
            self._cache_dir = os.getcwd()
        self._last_refresh = 0

        # if a cache directory was specified, find the latest files
        if self._cache_dir is not None:
            leapfile = self._find_latest_filename_in_dir(self._cache_dir, self._leapfile_prefix)
            # compute the timestamp
            self._last_refresh = self._extract_timestamp_from_filename(leapfile)

        # if files are too old (or missing), then refresh
        if _time.time() > self._last_refresh + self._refresh_seconds:
            self._refresh()

        # else load from the files
        else:
            with open(leapfile, 'rb') as f:
                leaptable_raw = f.read()
            self._build_leaptable(leaptable_raw)

        # compute some derived quantities
        self.tai_gps_epoch = self.utc_to_tai(self.utc_gps_epoch)
        self.tai_unix_epoch = self.utc_to_tai(self.utc_unix_epoch)


    def _find_latest_filename_in_dir(self, dirname, file_prefix):
        if not _ospath.isdir(dirname):
            raise RuntimeError("directory %s does not exist" % dirname)

        # find all files matching pattern
        candidates = [fn for fn in os.listdir(dirname) if fn.startswith(file_prefix)]

        # grab the latest one
        if len(sorted(candidates)) > 0:
            return candidates[-1]
        else:
            return None

    def _extract_timestamp_from_filename(self, fn):
        if fn is not None:
            m = _re.search(r'\d+$', fn)
            return int(m.group(0))
        else:
            return 0

    def _build_leaptable(self, leaptable_raw):
        self.leaptable = []
        
        lines = leaptable_raw.split('\n')
        for line in lines:
            tokens=line.split()
            if len(tokens) < 7:
                continue
            year = int(tokens[0])
            month = self._month_abbr_to_num[tokens[1]]
            day = int(tokens[2])
            tai_utc_difference = float(tokens[6])
            utc_dt = _datetime.datetime(year, month, day)
            tai_dt = utc_dt + _datetime.timedelta(seconds=tai_utc_difference)
            self.leaptable.append( (utc_dt, tai_dt, tai_utc_difference) )
        
    def _refresh(self):
        print("Fetching from %s" % self._leapfile_url)
        response = _urllib2.urlopen(self._leapfile_url)
        leaptable_raw = response.read()

        self._build_leaptable(leaptable_raw)
        self._last_refresh = int(_time.time())
        self._save_file(leaptable_raw)

    def _save_file(self, leaptable_raw):
        if self._cache_dir is None:
            return

        timestamp = str(self._last_refresh)
        leapfile = _ospath.join(self._cache_dir, self._leapfile_prefix + timestamp)

        with open(leapfile, 'wb') as f:
            f.write(leaptable_raw)

    def _tai_minus_utc_at_utc(self, utc_dt):
        # do we need to refresh the database?
        if _time.time() > self._last_refresh + self._refresh_seconds:
            self._refresh()

        leapseconds = 0
        for leaprec in self.leaptable:
            if leaprec[0] > utc_dt:
                break
            leapseconds = leaprec[2] 
        return leapseconds

    def _tai_minus_utc_at_tai(self, tai_dt):
        # do we need to refresh the database?
        if _time.time() > self._last_refresh + self._refresh_seconds:
            self._refresh()
        leapseconds = 0

        for leaprec in self.leaptable:
            if leaprec[1] > tai_dt:
                break
            leapseconds = leaprec[2] 
        return leapseconds

    def utc_to_tai(self, utc_dt):
        leapseconds = self._tai_minus_utc_at_utc(utc_dt)
        return utc_dt + _datetime.timedelta(seconds=leapseconds)

    def tai_to_utc(self, tai_dt):
        leapseconds = self._tai_minus_utc_at_tai(tai_dt)
        return tai_dt - _datetime.timedelta(seconds=leapseconds)

    def utc_to_unix(self, utc_dt):
        return (utc_dt-self.utc_unix_epoch).total_seconds()

    def unix_to_utc(self, timestamp):
        return _datetime.datetime.utcfromtimestamp(timestamp)

    def gps_to_tai(self, timestamp):
        return self.tai_gps_epoch + _datetime.timedelta(seconds=timestamp)

    def tai_to_gps(self, tai_dt):
        return (tai_dt - self.tai_gps_epoch).total_seconds()

    def gps_to_gpsdatetime(self, timestamp):
        return self.utc_gps_epoch + _datetime.timedelta(seconds=timestamp)

    def gpsdatetime_to_gps(self, gps_dt):
        return (gps_dt - self.utc_gps_epoch).total_seconds()


    # convenience conversions (derived from above)
    def gps_to_utc(self, timestamp):
        return self.tai_to_utc(self.gps_to_tai(timestamp))

    def utc_to_gps(self, utc_dt):
        return self.tai_to_gps(self.utc_to_tai(utc_dt))

    def gps_to_unix(self, timestamp):
        return self.utc_to_unix(self.gps_to_utc(timestamp))

    def unix_to_gps(self, timestamp):
        return self.utc_to_gps(self.unix_to_utc(timestamp))



if __name__ == '__main__':

    leap = LeapSecondConverter()

    utc_dt = _datetime.datetime.utcnow()
    print("UTC")
    print(utc_dt)

    tai_dt = leap.utc_to_tai(utc_dt)
    print("TAI")
    print(tai_dt)
    if utc_dt != leap.tai_to_utc(tai_dt):
        raise RuntimeError("Something is wrong with UTC <-> TAI conversion")

    unix = leap.utc_to_unix(utc_dt)
    print("Unix") 
    print(unix)
    if utc_dt != leap.unix_to_utc(unix):
        raise RuntimeError("Something is wrong with UTC <-> Unix conversion")

    gps = leap.tai_to_gps(tai_dt)
    print("GPS")
    print(gps)
    if tai_dt != leap.gps_to_tai(gps):
        raise RuntimeError("Something is wrong with TAI <-> GPS conversion")

    gps_dt = leap.gps_to_gpsdatetime(gps)
    print("GPS datetime")
    print(gps_dt)
    if gps != leap.gpsdatetime_to_gps(gps_dt):
        raise RuntimeError("Something is wrong with GPSdt <-> GPS conversion")
