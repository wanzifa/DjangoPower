import warnings
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured
from django.urls import (
    LocaleRegexURLResolver, RegexURLPattern, RegexURLResolver,
)
from django.utils import six
from django.utils.deprecation import RemovedInDjango20Warning

__all__ = ['handler400', 'handler403', 'handler404', 'handler500', 'include', 'url']

handler400 = 'django.views.defaults.bad_request'
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'


def include(arg, namespace=None, app_name=None):
    if app_name and not namespace:
        raise ValueError('Must specify a namespace if specifying app_name.')
    if app_name:
        warnings.warn(
            'The app_name argument to django.conf.urls.include() is deprecated. '
            'Set the app_name in the included URLconf instead.',
            RemovedInDjango20Warning, stacklevel=2
        )

    if isinstance(arg, tuple):
        # callable returning a namespace hint
        try:
            urlconf_module, app_name = arg
        except ValueError:
            if namespace:
                raise ImproperlyConfigured(
                    'Cannot override the namespace for a dynamic module that provides a namespace'
                )
            warnings.warn(
                'Passing a 3-tuple to django.conf.urls.include() is deprecated. '
                'Pass a 2-tuple containing the list of patterns and app_name, '
                'and provide the namespace argument to include() instead.',
                RemovedInDjango20Warning, stacklevel=2
            )
            urlconf_module, app_name, namespace = arg
    else:
        # No namespace hint - use manually provided namespace
        # 见得最多的就是url(xxx,include('xxx.urls'))这样的
        # arg对应的就是那个urls模块 
        urlconf_module = arg

    if isinstance(urlconf_module, six.string_types):
        # six.string_types对应的就是python2里面的字符串对象
        # 一旦发现是字符串对象 好 导入！
        # import_module 函数将会返回你想要的那个模块 同时导入这个模块
        urlconf_module = import_module(urlconf_module)
    #从导入的模块里获取我们想要的urlpatterns列表
    patterns = getattr(urlconf_module, 'urlpatterns', urlconf_module)
    app_name = getattr(urlconf_module, 'app_name', app_name)
    if namespace and not app_name:
        warnings.warn(
            'Specifying a namespace in django.conf.urls.include() without '
            'providing an app_name is deprecated. Set the app_name attribute '
            'in the included module, or pass a 2-tuple containing the list of '
            'patterns and app_name instead.',
            RemovedInDjango20Warning, stacklevel=2
        )

    namespace = namespace or app_name

    # Make sure we can iterate through the patterns (without this, some
    # testcases will break).
    #如果urlpatterns是一个可迭代的对象
    if isinstance(patterns, (list, tuple)):
        for url_pattern in patterns:
            # Test if the LocaleRegexURLResolver is used within the include;
            # this should throw an error since this is not allowed!
            # 这个LocaleRegexURLResolver类 我们之后再单独剖析它
            if isinstance(url_pattern, LocaleRegexURLResolver):
                raise ImproperlyConfigured(
                    'Using i18n_patterns in an included URLconf is not allowed.')
    # 返回元组 注意它格式是元组 我们下面有用
    return (urlconf_module, app_name, namespace)


def url(regex, view, kwargs=None, name=None):
    # 看到了吧 如果第二个参数是元组 也就是我们使用include()的情况！
    if isinstance(view, (list, tuple)):
        # For include(...) processing.
        urlconf_module, app_name, namespace = view
        # 和上面那个locale什么什么一样
        # 我们也把这个名字很长的类放到后面单独开第二弹去讲
        return RegexURLResolver(regex, urlconf_module, kwargs, app_name=app_name, namespace=namespace)
    elif callable(view):
        # 如果view是一个可调用对象 
        # 也就是对应了视图函数
        # 不在话下 把函数和正则表达式对应起来！
        return RegexURLPattern(regex, view, kwargs, name)
    else:
        raise TypeError('view must be a callable or a list/tuple in the case of include().')
