import sys
import webapp2
import json
import datetime
import logging

from models import Subscription, NotificationSource

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import mail

from feedparser import feedparser

class SubscribeHandler(webapp2.RequestHandler):

    def _set_response_headers(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Access-Control-Allow-Origin'] = self.request.headers['Origin']
        self.response.headers['Access-Control-Max-Age'] = '86400'
        self.response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, If-Match, If-Modified-Since, If-None-Match, If-Unmodified-Since, X-Requested-With, Cookie'
        self.response.headers['Access-Control-Allow-Credentials'] = 'true'

    def _handle(self,url,tags,latlon,radius,period):
        self._set_response_headers()

        user = users.get_current_user()

        if not user:
            response = { 'success': False, 'login': users.create_login_url(self.request.uri) }
        else:
            try:
                period = int(period)
            except:
                period = 86400
            try:
                radius = int(radius)
            except:
                radius = None
            src = NotificationSource.query( NotificationSource.url == url ).fetch(1)
            if len(src) == 1:
                src = src[0]
            else:
                src = NotificationSource( url = url )
                ndb.put_multi([src])

            conditions = [ Subscription.user == user, 
                           Subscription.source == src.key, 
                           Subscription.latlon == latlon, 
                           Subscription.radius == radius ]

            if tags is None:
                tags = []
            tags = [x for x in tags if len(x) > 0]
            if len(tags) > 0:
                conditions.append( ndb.AND(*[Subscription.tags == tag for tag in tags]) )

            subscription = Subscription.query( *conditions ).fetch(1)
            if len(subscription) == 1:
                subscription = subscription[0]
                subscription.period = period
            else:
                subscription = Subscription( user = user, source = src.key, 
                                             tags = tags, latlon = latlon, radius = radius, period = period, 
                                             next_poll=datetime.datetime.now(),
                                             last_read=datetime.datetime.now() )
            ndb.put_multi([subscription])
            response = { 'success': True, 'id': subscription.key.urlsafe() }
            
        return json.dumps(response)

    def options(self):
        self._set_response_headers()
        self.response.write('{}')

    def get(self):
        url = self.request.get('url')
        tags = self.request.get('tags')
        latlon = self.request.get('latlon')
        radius = self.request.get('radius')
        period = self.request.get('period')
        callback = self.request.get('callback')
        ret = self._handle(url,tags,latlon,radius,period)
        if callback is not None and callback != '':
            self.response.write('%s(%s);' % (callback, ret))
        else:
            self.response.write(ret)
        
    def post(self):
        body = json.loads( self.request.body )
        url = body['url']
        tags = body.get('tags').split(',')
        latlon = body.get('latlon')
        radius = body.get('radius')
        period = body.get('period')
        ret = self._handle(url,tags,latlon,radius,period)
        self.response.write(ret)

class PollRssHandler(webapp2.RequestHandler):

    def send_mail(self,subscription,feed,maxpublished):
        to_send = []
        for entry in feed.entries:
            if entry.published_parsed <= subscription.last_read:
                continue
            if entry.pkw_tags is not None and subscription.tags is not None and len(subscription.tags) > 0:
                if len(entry.pkw_tags & set(subscription.tags)) == 0:
                    continue
            to_send.append( entry )
        
        if len(to_send) == 0:
            return

        now = datetime.datetime.now()
        while subscription.next_poll < now:
            subscription.next_poll += datetime.timedelta(seconds = subscription.period)
        subscription.last_read = maxpublished
        ndb.put_multi([subscription])

        logging.log(logging.DEBUG,"about to send: %r,%r" % (subscription,to_send))
        sender = "noreply@hasadna-notifications.appspotmail.com"
        logging.log(logging.DEBUG,"Sender email: %s" % sender)
        try:
            subtitle = "%s\n\n" % feed.feed.subtitle
        except:
            subtitle = ''
        mail.send_mail(sender="Hasadna Notification Center <%s>" % sender,
                       to=subscription.user.email(),
                       subject="Updates from: %s" % feed.feed.title,
                       body= subtitle + "\n---\n".join("\n".join([x.title,x.description,x.link]) for x in to_send),
                       html="<h2>%s</h2>" % subtitle + "<hr/>".join("<br/>".join([x.title,x.description,x.link]) for x in to_send)
                       )

    def get(self):
        for src in NotificationSource.query():
            logging.log(logging.INFO, "src=%s" % src.url)
            url = src.url

            data = urlfetch.fetch(url)
            feed = feedparser.parse(data.content)

            if feed.feed.title != src.title:
                src.title = feed.feed.title
                ndb.put_multi([src])

            maxpublished = datetime.datetime.fromtimestamp(0)
            logging.log(logging.INFO, "#entries=%s" % len(feed.entries))
            for entry in feed.entries:
                try:
                    entry.published_parsed = datetime.datetime(*entry.published_parsed[:6])
                    if maxpublished is None:
                        maxpublished = entry.published_parsed
                    else:
                        maxpublished = max(maxpublished,entry.published_parsed)
                except:
                    entry.published_parsed = None

                if hasattr(entry,'pkw_tags'):
                    entry.pkw_tags = set(entry.pkw_tags.split(','))
                else:
                    entry.pkw_tags = None
            logging.log(logging.INFO, "#maxpublished=%r" % maxpublished)

            if maxpublished is None:
                logging.log(logging.WARN, "Could not get published date for feed %s" % url)
                continue

            now = datetime.datetime.now()
            subscriptions = Subscription.query( Subscription.next_poll < now, 
                                                Subscription.source == src.key )

            for subscription in subscriptions:
                logging.log(logging.DEBUG, "subscription=%r" % subscription)
                self.send_mail( subscription, feed, maxpublished )
        

app = webapp2.WSGIApplication([
    ('/api/subscribe', SubscribeHandler),
    ('/tasks/pollrss', PollRssHandler)
], debug=True)
