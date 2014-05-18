class HN

  subscribe: ( url, tags, latlon, radius, period, success_cb, login_cb ) ->
    apiurl = 'http://hasadna-notifications.appspot.com/api/subscribe'
    data =
      url   : url
      tags  : tags
      period: parseInt(period)
      latlon: latlon
      radius: if radius? and radius != "" then parseInt(radius) else null
    data = JSON.stringify data

    invocation = new XMLHttpRequest()

    handler =  ->
      if invocation.readyState != 4
        return
      response = invocation.response
      if response.success
        key = response.id
        success_cb( key )
      else
        url = response.login
        login_cb(url)

    if invocation
      invocation.open 'POST', apiurl, true
      invocation.setRequestHeader 'Content-Type', 'application/json'
      invocation.responseType = 'json'
      invocation.onreadystatechange = handler
      invocation.withCredentials = true
      invocation.send data

  unsubscribe: ( key, success_cb, login_cb ) ->
    apiurl = 'http://hasadna-notifications.appspot.com/api/unsubscribe'
    data =
      subscription_id   : key
    data = JSON.stringify data

    invocation = new XMLHttpRequest()

    handler = ->
      if invocation.readyState != 4
        return
      response = invocation.response
      if response.success
        success_cb()
      else
        url = response.login
        login_cb(url)

    if invocation
      invocation.open 'POST', apiurl, true
      invocation.setRequestHeader 'Content-Type', 'application/json'
      invocation.responseType = 'json'
      invocation.onreadystatechange = handler
      invocation.withCredentials = true
      invocation.send data

  issubscribed: ( url, tags, latlon, success_cb, login_cb ) ->
    apiurl = 'http://hasadna-notifications.appspot.com/api/issubscribed'
    data =
        url   : url
        tags  : tags
        latlon: latlon
    data = JSON.stringify data

    invocation = new XMLHttpRequest()

    handler = ->
      if invocation.readyState != 4
        return
      response = invocation.response
      if response.login?
        url = response.login
        login_cb(url)
      else
        success_cb(response.success,response.id)

    if invocation
      invocation.open 'POST', apiurl, true
      invocation.setRequestHeader 'Content-Type', 'application/json'
      invocation.responseType = 'json'
      invocation.onreadystatechange = handler
      invocation.withCredentials = true
      invocation.send data

window.hn = new HN()
