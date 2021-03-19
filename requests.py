import urllib
import urllib2


class Response(object):
    def __init__(self, content):
        self.text = content.decode('utf-8')


def get(url, params=None):
    if params:
        params = [(k, v.encode('utf-8')) for k, v in params.items()]
        url = url + '?' + urllib.urlencode(params)
    contents = urllib.urlopen(url).read()
    return Response(contents)


def post(url, data=None):
    if data:
        data = urllib.urlencode(data)
    contents = urllib2.urlopen(url, data=data).read()
    return Response(contents)


if __name__ == '__main__':
    response = post('https://httpbin.org/post', {'q': 'python'})
    print response.text
