import sys
import webapp2
import json
import datetime
import logging
import pystache

from models import Subscription, NotificationSource

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import mail

from feedparser import feedparser

class APIHandler(webapp2.RequestHandler):

    def _set_response_headers(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Access-Control-Allow-Origin'] = self.request.headers['Origin']
        self.response.headers['Access-Control-Max-Age'] = '86400'
        self.response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, If-Match, If-Modified-Since, If-None-Match, If-Unmodified-Since, X-Requested-With, Cookie'
        self.response.headers['Access-Control-Allow-Credentials'] = 'true'

    def _loginURL(self):
        if self.request.method == "GET":
          return users.create_login_url(self.request.uri)
        else:
          return users.create_login_url("/static/loggedin.html")

    def options(self):
        self._set_response_headers()
        self.response.write('{}')

    def get(self):
        params = [ self.request.get(p) for p in self._params() ]
        callback = self.request.get('callback')
        ret = self._handle(*params)
        if callback is not None and callback != '':
            self.response.write('%s(%s);' % (callback, ret))
        else:
            self.response.write(ret)

    def post(self):
        body = json.loads( self.request.body )
        params = [ body.get(p) for p in self._params() ]
        ret = self._handle(*params)
        self.response.write(ret)

class UnSubscribeHandler(APIHandler):

    def _params(self):
        return ['subscription_id']

    def _handle(self,subscription_id):
        self._set_response_headers()

        user = users.get_current_user()

        if not user:
            response = { 'success': False, 'login': self._loginURL() }
        else:
            success = False
            key = ndb.Key(urlsafe=subscription_id)
            if key.kind() == "Subscription":
                subscription = key.get()
                if subscription.user == user:
                    key.delete()
                    success = True
            response = { 'success': success }
        return json.dumps(response)


class SubscribeHandler(APIHandler):

    def _params(self):
        return ['url','tags','latlon','radius','period']

    def _handle(self,url,tags,latlon,radius,period):
        self._set_response_headers()

        user = users.get_current_user()

        if not user:
            response = { 'success': False, 'login': self._loginURL() }
        else:
            try:
                period = int(period)
            except:
                period = 86400
            try:
                radius = int(radius)
            except:
                radius = None

            if tags is not None:
                tags = tags.split(',')
            else:
                tags = []

            tags = [x for x in tags if len(x) > 0]

            try:
                if latlon is not None:
                    latlon = latlon.split(",")
                    lat = float(latlon[0])
                    lon = float(latlon[1])
                    latlon = db.GeoPt(lat,lon)
            except:
                latlon = None

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
                                             last_read=datetime.datetime.now() - datetime.timedelta(hours=3) )
            ndb.put_multi([subscription])
            response = { 'success': True, 'id': subscription.key.urlsafe() }

        return json.dumps(response)

class IsSubscribedHandler(APIHandler):

    def _params(self):
        return ['url','tags','latlon']

    def _handle(self,url,tags,latlon):
        self._set_response_headers()

        user = users.get_current_user()

        if not user:
            response = { 'success': False, 'login': self._loginURL() }
        else:
            response = { 'success': False }
            if tags is not None:
                tags = tags.split(',')
            else:
                tags = []

            tags = [x for x in tags if len(x) > 0]

            src = NotificationSource.query( NotificationSource.url == url ).fetch(1)
            if len(src) == 1:
                src = src[0]
                conditions = [ Subscription.user == user,
                               Subscription.source == src.key,
                               Subscription.latlon == latlon ]
                if len(tags) > 0:
                  conditions.append( ndb.AND(*[Subscription.tags == tag for tag in tags]) )

                subscription = Subscription.query( *conditions ).fetch(1)
                if len(subscription) == 1:
                  subscription = subscription[0]
                  response = { 'success': True, 'id': subscription.key.urlsafe() }

        return json.dumps(response)


class PollRssHandler(webapp2.RequestHandler):

    TEXT_TEMPLATE = file('text.mustache').read()
    HTML_TEMPLATE = file('html.mustache').read()

    def send_mail(self,subscription,feed,maxpublished):
        to_send = []
        for entry in feed.entries:
            if entry.published_parsed <= subscription.last_read:
                logging.debug("too old (%r)" % entry)
                continue
            if entry.pkw_tags is not None and subscription.tags is not None and len(subscription.tags) > 0:
                if len(entry.pkw_tags & set(subscription.tags)) == 0:
                    logging.debug("no tags %r (%r)" % (entry,subscription.tags))
                    continue
            to_send.append( entry )
        to_send.sort(key=lambda e:e.pkw_score )

        if len(to_send) == 0:
            logging.debug("nothing new to send...")
            return

        now = datetime.datetime.now()
        while subscription.next_poll < now:
            subscription.next_poll += datetime.timedelta(seconds = subscription.period)
        subscription.last_read = maxpublished

        logging.log(logging.DEBUG,"about to send: %r,%r" % (subscription,to_send))
        sender = "noreply@hasadna-notifications.appspotmail.com"
        logging.log(logging.DEBUG,"Sender email: %s" % sender)

        template_data = { 'feed': feed.feed, 'entries': to_send }
        logging.info("%r" % template_data)

        text_template = self.TEXT_TEMPLATE
        html_template = self.HTML_TEMPLATE
        if hasattr(feed,'pkw_text_template'):
            text_template = feed.pkw_text_template
        if hasattr(feed,'pkw_html_template'):
            html_template = feed.pkw_html_template

        mail.send_mail(sender="Hasadna Notification Center <%s>" % sender,
                       to=subscription.user.email(),
                       subject="Updates from: %s" % feed.feed.title,
                       body=pystache.render(text_template,template_data),
                       html=pystache.render(html_template,template_data),
                    #    body= subtitle + "\n---\n".join("\n".join([x.title,x.description,x.link]) for x in to_send),
                    #    html="<h2>%s</h2>" % subtitle + "<hr/>".join("<br/>".join(["<b>"+x.title+"</b>",x.description,x.link]) for x in to_send)
                       )

        ndb.put_multi([subscription])

    def handle_single_source(self,src):
        url = src.url

        try:
            data = urlfetch.fetch(url)
        except:
            logging.log(logging.WARN, "Failed to fetch url %s" % url)
            return
        feed = feedparser.parse(data.content)

        current_title = None
        try:
            current_title = src.title
        except:
            pass
        if hasattr(feed.feed,'title'):
            if feed.feed.title != current_title:
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

            if hasattr(entry,'pkw_score'):
                entry.pkw_score = float(entry.pkw_score)
            else:
                entry.pkw_score = 1
        logging.log(logging.INFO, "#maxpublished=%r" % maxpublished)

        if maxpublished is None:
            logging.log(logging.WARN, "Could not get published date for feed %s" % url)
            return

        now = datetime.datetime.now()
        subscriptions = Subscription.query( Subscription.next_poll < now,
                                            Subscription.source == src.key )

        for subscription in subscriptions:
            logging.log(logging.DEBUG, "subscription=%r" % subscription)
            self.send_mail( subscription, feed, maxpublished )


    def get(self):
        for src in NotificationSource.query():
            logging.log(logging.INFO, "src=%s" % src.url)
            try:
                self.handle_single_source(src)
            except Exception,e:
                logging.log(logging.ERROR, "src=%s, err=%s" % (src.url,e))


app = webapp2.WSGIApplication([
    ('/api/subscribe', SubscribeHandler),
    ('/api/issubscribed', IsSubscribedHandler),
    ('/api/unsubscribe', UnSubscribeHandler),
    ('/tasks/pollrss', PollRssHandler)
], debug=True)
