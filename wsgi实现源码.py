"""
首先，这个脚本是跑不起来的啊哈哈哈
之前的webserver还有python复习笔记都用了可运行脚本＋中文注释的形式，可读性还是比较强的
这次主要是将django源码中与wsgi实现相关的几个类贴进来，讲一讲它们之间是如何交互，从而实现接收请求与返回响应这个流程的
"""

"""
第一部分
django.core.servers模块中的wsgi.py文件
"""
import django
#重点就是这个WSGIHandler类了 
from django.core.handlers.wsgi import WSGIHandler


def get_wsgi_application():
    """
    The public interface to Django's WSGI support. Should return a WSGI
    callable.

    Allows us to avoid making django.core.handlers.WSGIHandler public API, in
    case the internal WSGI implementation changes or moves in the future.
    """
    #利用setup函数做配置方面的设置
    django.setup(set_prefix=False)
    #返回一个WSGIHandler实例 下面我们就来研究这个类
    return WSGIHandler()

"""
第二部分 
WSGIhandler类
它的实例就是一个wsgi app
位于django.core.handlers包的wsgi模块
"""
class WSGIHandler(base.BaseHandler):
    #定义一个线程锁对象
    initLock = Lock()
    # WSGI类是对HttpRequest的进一步封装
    # 这里不用太在意
    # 第四部分会讲一下
    request_class = WSGIRequest
    
    # 这个call方法将WSGIHandler的实例变成一个可调用对象
    # 熟悉WSGI的小伙伴们 看到参数名是不是明白了些什么?
    # 没错 这个类的实例就是一个不折不扣的wsgi app!
    def __call__(self, environ, start_response):
        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        # 中文的是我的 英文的是源码自己的注释
        # 这里_request_middleware是从父类继承来的属性
        # 对于父类BaseHandler 我们会在第三部分讲解它的部分源码
        if self._request_middleware is None:
            # tip:
            # 从with语句的使用我们得知，Lock对象具有__enter__和__exit__方法
            with self.initLock:
                # Check that middleware is still uninitialized.
                if self._request_middleware is None:
                    self.load_middleware()
        
        set_script_prefix(get_script_name(environ))
        signals.request_started.send(sender=self.__class__, environ=environ)
        try:
            request = self.request_class(environ)
        except UnicodeDecodeError:
            logger.warning('Bad Request (UnicodeDecodeError)',
                exc_info=sys.exc_info(),
                extra={
                    'status_code': 400,
                }
            )
            response = http.HttpResponseBadRequest()
        else:
            response = self.get_response(request)

        response._handler_class = self.__class__
        
        #下面就全是往一个reponse中写信息的操作了
        status = '%s %s' % (response.status_code, response.reason_phrase)
        response_headers = [(str(k), str(v)) for k, v in response.items()]
        for c in response.cookies.values():
            response_headers.append((str('Set-Cookie'), str(c.output(header=''))))
        start_response(force_str(status), response_headers)
        if getattr(response, 'file_to_stream', None) is not None and environ.get('wsgi.file_wrapper'):
            response = environ['wsgi.file_wrapper'](response.file_to_stream)
        return response


"""
介绍WSGIHandler的父类
BaseHandler
"""

class BaseHandler(object):
    # Changes that are always applied to a response (in this order).
    response_fixes = [
        http.conditional_content_removal,
    ]

    def __init__(self):
        self._request_middleware = None
        self._view_middleware = None
        self._template_response_middleware = None
        self._response_middleware = None
        self._exception_middleware = None
    
    #加载中间件
    def load_middleware(self):
        """
        Populate middleware lists from settings.MIDDLEWARE_CLASSES.

        Must be called after the environment is fixed (see __call__ in subclasses).
        """
        self._view_middleware = []
        self._template_response_middleware = []
        self._response_middleware = []
        self._exception_middleware = []

        request_middleware = []
        #导入中间件
        for middleware_path in settings.MIDDLEWARE_CLASSES:
            mw_class = import_string(middleware_path)
            try:
                #实例化中间件对象
                mw_instance = mw_class()
            except MiddlewareNotUsed as exc:
                if settings.DEBUG:
                    if six.text_type(exc):
                        logger.debug('MiddlewareNotUsed(%r): %s', middleware_path, exc)
                    else:
                        logger.debug('MiddlewareNotUsed: %r', middleware_path)
                continue
            
            # 关注一下request_middleware
            # 看到了吧 它其实是所有中间件的process_request函数集合
            # 我们可以看到所有的所谓中间件函数，都是预处理或后处理函数的集合
            # 关于process_request函数 我们会在README文件中进一步解释
            if hasattr(mw_instance, 'process_request'):
                request_middleware.append(mw_instance.process_request)
            if hasattr(mw_instance, 'process_view'):
                self._view_middleware.append(mw_instance.process_view)
            if hasattr(mw_instance, 'process_template_response'):
                self._template_response_middleware.insert(0, mw_instance.process_template_response)
            if hasattr(mw_instance, 'process_response'):
                self._response_middleware.insert(0, mw_instance.process_response)
            if hasattr(mw_instance, 'process_exception'):
                self._exception_middleware.insert(0, mw_instance.process_exception)

        # We only assign to this when initialization is complete as it is used
        # as a flag for initialization being complete.
        self._request_middleware = request_middleware
"""
中间省略许多行
我们来看get_response函数
"""
    def get_response(self, request):
        "Returns an HttpResponse object for the given HttpRequest"

        # Setup default url resolver for this thread, this code is outside
        # the try/except so we don't get a spurious "unbound local
        # variable" exception in the event an exception is raised before
        # resolver is set
        urlconf = settings.ROOT_URLCONF
        set_urlconf(urlconf)
        # get_resolver会返回一个RegexURLResolver实例
        resolver = get_resolver(urlconf)
        # Use a flag to check if the response was rendered to prevent
        # multiple renderings or to force rendering if necessary.
        response_is_rendered = False
        try:
            response = None
            # Apply request middleware
            # 请求中间件开始发挥威力了
            # for循环将遍历每一个中间件中的process_request对象
            # 直到某一个中间件的process_request返回了一个response 
            # 那么停止遍历 返回response对象
            for middleware_method in self._request_middleware:
                response = middleware_method(request)
                if response:
                    break
            
            # 啥？上面遍历完没有返回response？
            # 那就继续往下走 进入下一个中间件
            if response is None:
                if hasattr(request, 'urlconf'):
                    # Reset url resolver with a custom URLconf.
                    urlconf = request.urlconf
                    set_urlconf(urlconf)
                    resolver = get_resolver(urlconf)
                
                # 调用ResolverMatch对象中的resolve方法
                # 返回ResolverMatch对象
                # 获取响应函数
                resolver_match = resolver.resolve(request.path_info)
                callback, callback_args, callback_kwargs = resolver_match
                request.resolver_match = resolver_match

                # Apply view middleware
                for middleware_method in self._view_middleware:
                    response = middleware_method(request, callback, callback_args, callback_kwargs)
                    if response:
                        break

            if response is None:
                wrapped_callback = self.make_view_atomic(callback)
                try:
                    response = wrapped_callback(request, *callback_args, **callback_kwargs)
                except Exception as e:
                    response = self.process_exception_by_middleware(e, request)

            # Complain if the view returned None (a common error).
            if response is None:
                if isinstance(callback, types.FunctionType):    # FBV
                    view_name = callback.__name__
                else:                                           # CBV
                    view_name = callback.__class__.__name__ + '.__call__'
                raise ValueError("The view %s.%s didn't return an HttpResponse object. It returned None instead."
                                 % (callback.__module__, view_name))

            # If the response supports deferred rendering, apply template
            # response middleware and then render the response
            # 如果response需要渲染页面
            # 那么利用template中间件去给它一个渲染的处理
            if hasattr(response, 'render') and callable(response.render):
                for middleware_method in self._template_response_middleware:
                    response = middleware_method(request, response)
                    # Complain if the template response middleware returned None (a common error).
                    if response is None:
                        raise ValueError(
                            "%s.process_template_response didn't return an "
                            "HttpResponse object. It returned None instead."
                            % (middleware_method.__self__.__class__.__name__))
                try:
                    response = response.render()
                except Exception as e:
                    response = self.process_exception_by_middleware(e, request)

                response_is_rendered = True

        except http.Http404 as exc:
            logger.warning('Not Found: %s', request.path,
                        extra={
                            'status_code': 404,
                            'request': request
                        })
            if settings.DEBUG:
                response = debug.technical_404_response(request, exc)
            else:
                response = self.get_exception_response(request, resolver, 404, exc)

        except PermissionDenied as exc:
            logger.warning(
                'Forbidden (Permission denied): %s', request.path,
                extra={
                    'status_code': 403,
                    'request': request
                })
            response = self.get_exception_response(request, resolver, 403, exc)

        except MultiPartParserError as exc:
            logger.warning(
                'Bad request (Unable to parse request body): %s', request.path,
                extra={
                    'status_code': 400,
                    'request': request
                })
            response = self.get_exception_response(request, resolver, 400, exc)

        except SuspiciousOperation as exc:
            # The request logger receives events for any problematic request
            # The security logger receives events for all SuspiciousOperations
            security_logger = logging.getLogger('django.security.%s' %
                            exc.__class__.__name__)
            security_logger.error(
                force_text(exc),
                extra={
                    'status_code': 400,
                    'request': request
                })
            if settings.DEBUG:
                return debug.technical_500_response(request, *sys.exc_info(), status_code=400)

            response = self.get_exception_response(request, resolver, 400, exc)

        except SystemExit:
            # Allow sys.exit() to actually exit. See tickets #1023 and #4701
            raise

        except Exception:  # Handle everything else.
            # Get the exception info now, in case another exception is thrown later.
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

        try:
            # Apply response middleware, regardless of the response
            for middleware_method in self._response_middleware:
                response = middleware_method(request, response)
                # Complain if the response middleware returned None (a common error).
                if response is None:
                    raise ValueError(
                        "%s.process_response didn't return an "
                        "HttpResponse object. It returned None instead."
                        % (middleware_method.__self__.__class__.__name__))
            response = self.apply_response_fixes(request, response)
        except Exception:  # Any exception should be gathered and handled
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

        response._closable_objects.append(request)

        # If the exception handler returns a TemplateResponse that has not
        # been rendered, force it to be rendered.
        if not response_is_rendered and callable(getattr(response, 'render', None)):
            response = response.render()

        return response

"""
下面介绍一下WSGIRequest对象
"""

class WSGIRequest(http.HttpRequest):
    def __init__(self, environ):
        #从环境参数中获取django app的名字（包的名字）
        script_name = get_script_name(environ)
        # 从环境参数中获取路径信息
        path_info = get_path_info(environ)
        # 如果没有路径信息 那么就在包名的后面加斜杠来作为url
        if not path_info:
            # Sometimes PATH_INFO exists, but is empty (e.g. accessing
            # the SCRIPT_NAME URL without a trailing slash). We really need to
            # operate as if they'd requested '/'. Not amazingly nice to force
            # the path like this, but should be harmless.
            path_info = '/'
        self.environ = environ
        self.path_info = path_info
        # be careful to only replace the first slash in the path because of
        # http://test/something and http://test//something being different as
        # stated in http://www.ietf.org/rfc/rfc2396.txt
        #设定url
        self.path = '%s/%s' % (script_name.rstrip('/'),
                               path_info.replace('/', '', 1))
        self.META = environ
        self.META['PATH_INFO'] = path_info
        self.META['SCRIPT_NAME'] = script_name
        self.method = environ['REQUEST_METHOD'].upper()
        self.content_type, self.content_params = cgi.parse_header(environ.get('CONTENT_TYPE', ''))
        if 'charset' in self.content_params:
            try:
                codecs.lookup(self.content_params['charset'])
            except LookupError:
                pass
            else:
                self.encoding = self.content_params['charset']
        self._post_parse_error = False
        try:
            content_length = int(environ.get('CONTENT_LENGTH'))
        except (ValueError, TypeError):
            content_length = 0
        self._stream = LimitedStream(self.environ['wsgi.input'], content_length)
        self._read_started = False
        self.resolver_match = None

    def _get_scheme(self):
        return self.environ.get('wsgi.url_scheme')

    @cached_property
    def GET(self):
        # The WSGI spec says 'QUERY_STRING' may be absent.
        raw_query_string = get_bytes_from_wsgi(self.environ, 'QUERY_STRING', '')
        return http.QueryDict(raw_query_string, encoding=self._encoding)

    def _get_post(self):
        if not hasattr(self, '_post'):
            self._load_post_and_files()
        return self._post

    def _set_post(self, post):
        self._post = post

    @cached_property
    def COOKIES(self):
        raw_cookie = get_str_from_wsgi(self.environ, 'HTTP_COOKIE', '')
        return http.parse_cookie(raw_cookie)

    def _get_files(self):
        if not hasattr(self, '_files'):
            self._load_post_and_files()
        return self._files

    POST = property(_get_post, _set_post)
    FILES = property(_get_files)
