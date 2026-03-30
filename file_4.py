import time


class HtmlWrapDecorator:
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # ведение истории вызовов исходной функции
            cur_time = time.asctime()
            func_name = ": function " + func.__name__
            arguments = " called with arguments " + ', '.join(map(str, kwargs.keys()))
            print(cur_time + func_name + arguments)

            print("<html>\n\t<body>")
            result = func(*args, **kwargs)
            print("\t</body>\n</html>")
            return result


        return wrapper


class TimerDecorator:
    def __call__(self, func):
        @HtmlWrapDecorator()
        def wrapper(*args, **kwargs):
            # ведение истории вызовов исходной функции
            cur_time = time.asctime()
            func_name = ": function " + func.__name__
            arguments = " called with arguments " + ', '.join(map(str, kwargs.keys()))
            print("\t\t" + cur_time + func_name + arguments)

            # подсчет времени выполнения исходной функции
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            print("\t\tfunction time: " + str(end - start))
            return result

        return wrapper


@TimerDecorator()
def powers_for(ls, len):
    buf = []
    for i in range(len):
        buf.append(pow(ls[i], 2))
    return buf


@TimerDecorator()
def powers_comp(ls, length):
    buf = [i*i for i in range(length)]
    return buf


@TimerDecorator()
def powers_map(ls):
    buf = list(map(lambda x: x*x, ls))
    return buf


if __name__ == "__main__":
    length = 100000

    nums = []
    for i in range(length):
        nums.append(i)

    print("\n---FOR---")
    res_1 = powers_for(ls=nums, len=length)

    print("\n---LIST COMPREHENSION---")
    res_2 = powers_comp(ls=nums, length=length)

    print("\n---MAP---")
    res_3 = powers_map(ls=nums)
