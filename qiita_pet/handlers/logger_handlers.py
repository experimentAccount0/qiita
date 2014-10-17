from __future__ import division

from tornado.web import authenticated

from .base_handlers import BaseHandler
from qiita_db.logger import LogEntry
from qiita_db.user import User
from tornado.web import HTTPError


class LogEntryViewerHandler(BaseHandler):
    def _check_access(self):
        if User(self.current_user).level not in {'admin', 'dev'}:
            raise HTTPError(405, "User %s doesn't have sufficient privileges "
                            "to view error page" % self.current_user)

    @authenticated
    def get(self):
        self._check_access()
        logentries = LogEntry.newest_records()
        self.render("error_log.html", logentries=logentries,
                    user=self.current_user)

    @authenticated
    def post(self):
        self._check_access()
        numentries = int(self.get_argument("numrecords"))
        if numentries < 0:
            numentries = 100
        logentries = LogEntry.newest_records(numentries)
        self.render("error_log.html", logentries=logentries,
                    user=self.current_user)
