notification-center
===================

Centralized Notification Center for all Projects

Allows users to subscribe on projects' event streams.
Projects just need to expose RSS feeds with the events, notifications etc.

The notification server does all the user authentication, RSS feed polling, filtering by tags or lat/lon (for projects who need it), and send an aggregated email to the user - at the frequency the project or user required.

API
---

** General **

All API commands work wither with GET or POST.

For **GET**, parameters are passed in the URL as query parameters.
You can add a `callback` parameter for JSONP access.

For **POST**, parameters are passed as a JSON object in the request's body.

All commands return a JSON object with the command's reponse. All reponses contain a boolean `success` indicating the command's success, and possibly additional fields.


** Subscribe to a feed **

    /api/subscribe

Subscribes a user to a specific notification.

*Parameters*:

* `url` :

  URL of RSS feed to subscribe to.

* `period` :

  Minimal time (in seconds) between consecutive emails sent to the user in this subscription.

* `tags` :

  Comma delimited list of tags to filter.
  If not specified, not filtering by tags will be performed.

* `latlon` :

  Tuple of floats separated by a comma, indicating a geo-filter for this feed around this location. Example: `32.8,34.2`

* `radius` :

  Numeric value (in meters), used alongside the `latlon` parameter to specify the search radius for the geo-filtering. If one of `latlon` or `radius` is not specified, no geo-filtering will be performed.

*Response*:

* `id` :

  identification string for the subscription.
  Can be used to unsubscribe later.

** Unsubscribe from a feed **

    /api/unsubscribe

Unsubscribes a user from a specific notification.

*Parameters*:

* `subscription_id` :

  Identification string of the subscription.

*Response*:

(none)

RSS Format
----------

We support all flavours of RSS and ATOM although currently tested on RSS 2.0 only.

Permitted and useful tags are:

- `feed.title`
- `feed.subtitle`
- `item.pubDate`
- `item.title`
- `item.description`
- `item.link`
