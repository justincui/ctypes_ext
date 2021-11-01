from collections.abc import Mapping


class _ConstPropValue:
    def __init__(self, prop_name, value):
        self._prop_name = prop_name
        self._value = value

    def __get__(self, instance, owner):
        return self._value

    def __set__(self, instance, value):
        raise AttributeError(
            'field of const object may not be assigned: {} <= {} (@obj={})'.format(self._prop_name, value, instance))

    def __delete__(self, instance):
        raise AttributeError('field of const object may not be assigned: {} (@obj={})'.format(self, instance))


def const_obj(obj, **kwargs):
    if isinstance(obj, Mapping):
        input = dict(obj)
    elif hasattr(obj, '__dict__') or hasattr(obj, '__slots__'):
        input = {k: getattr(obj, k) for k in dir(obj) if not k.startswith('__')}
    else:
        input = {}

    input.update(kwargs)

    clz = type('ConstObj', tuple(), {
        '__slots__': input.keys(),
        '__contains__': lambda self, key: key in self.__slots__,
        '__getitem__': lambda self, key: getattr(self, key, None),
        '__iter__': lambda self: iter((k, getattr(self, k)) for k in self.__slots__),   # NOTE: make objects created by const_obj can be converted to dict() with dict(the_const_object)
        '__eq__': lambda self, instance: self is instance or (
                hasattr(instance, '__slots__')
                and self.__slots__ == instance.__slots__
                and all(getattr(self, k) == getattr(instance, k) for k in self.__slots__)
        )
    })
    for k, v in input.items():
        setattr(clz, k, _ConstPropValue(k, v))
    return clz()


#######################################################################
if __name__ == '__main__':
    m = const_obj(dict(a=1, b=2), c=3, d=4)
    assert(dict(m) == dict(a=1, b=2, c=3, d=4))
    assert (m['c'] == 3)

    n = const_obj(dict(d=4, b=2), c=3, a=1)
    assert(m == n)

    assert('a' in m)
    assert('d' in m)

