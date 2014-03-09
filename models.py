from google.appengine.ext import ndb

class NotificationSource(ndb.Model):
    """Text Search index"""
    url = ndb.StringProperty()
    title = ndb.StringProperty()
    project_id = ndb.StringProperty()

class Subscription(ndb.Model):
    """A single subscription"""
    user = ndb.UserProperty()
    
    # Source
    source = ndb.KeyProperty(kind=NotificationSource)              ## URL for RSS feed
    
    # Filters
    tags = ndb.StringProperty(repeated=True)
    latlon = ndb.GeoPtProperty()
    radius = ndb.IntegerProperty()

    # Polling Settings
    period = ndb.IntegerProperty()
    next_poll = ndb.DateTimeProperty()
    last_read = ndb.DateTimeProperty()


