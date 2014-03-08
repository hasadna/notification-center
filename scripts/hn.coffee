class HN

        subscribe: ( url, tags, period, success_cb, login_cb ) ->
                apiurl = 'http://hasadna-notifications.appspot.com/api/subscribe'
                data =
                        url   : url
                        tags  : tags
                        period: period
                data = JSON.stringify data

                invocation = new XMLHttpRequest()

                handler = () ->

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


window.hn = new HN()
    