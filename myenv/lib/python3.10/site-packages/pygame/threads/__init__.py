"""
* Experimental *

Like the map function, but can use a pool of threads.

Really easy to use threads.  eg.  tmap(f, alist)

If you know how to use the map function, you can use threads.
"""

__author__ = "Rene Dudfield"
__version__ = "0.3.0"
__license__ = "Python license"

from queue import Queue, Empty
import threading


Thread = threading.Thread

STOP = object()
FINISH = object()

# DONE_ONE = object()
# DONE_TWO = object()

# a default worker queue.
_wq = None

# if we are using threads or not.  This is the number of workers.
_use_workers = 0

# Set this to the maximum for the amount of Cores/CPUs
#    Note, that the tests early out.
#    So it should only test the best number of workers +2
MAX_WORKERS_TO_TEST = 64


def init(number_of_workers=0):
    """Does a little test to see if threading is worth it.
      Sets up a global worker queue if it's worth it.

    Calling init() is not required, but is generally better to do.
    """
    global _wq, _use_workers

    if number_of_workers:
        _use_workers = number_of_workers
    else:
        _use_workers = benchmark_workers()

    # if it is best to use zero workers, then use that.
    _wq = WorkerQueue(_use_workers)


def quit():
    """cleans up everything."""
    global _wq, _use_workers
    _wq.stop()
    _wq = None
    _use_workers = False


def benchmark_workers(a_bench_func=None, the_data=None):
    """does a little test to see if workers are at all faster.
    Returns the number of workers which works best.
    Takes a little bit of time to run, so you should only really call
      it once.
    You can pass in benchmark data, and functions if you want.
    a_bench_func - f(data)
    the_data - data to work on.
    """
    # TODO: try and make this scale better with slower/faster cpus.
    #  first find some variables so that using 0 workers takes about 1.0 seconds.
    #  then go from there.

    # note, this will only work with pygame 1.8rc3+
    # replace the doit() and the_data with something that releases the GIL

    import pygame
    import pygame.transform
    import time

    if not a_bench_func:

        def doit(x):
            return pygame.transform.scale(x, (544, 576))

    else:
        doit = a_bench_func

    if not the_data:
        thedata = [pygame.Surface((155, 155), 0, 32) for x in range(10)]
    else:
        thedata = the_data

    best = time.time() + 100000000
    best_number = 0
    # last_best = -1

    for num_workers in range(0, MAX_WORKERS_TO_TEST):
        wq = WorkerQueue(num_workers)
        t1 = time.time()
        for _ in range(20):
            print(f"active count:{threading.active_count()}")
            tmap(doit, thedata, worker_queue=wq)
        t2 = time.time()

        wq.stop()

        total_time = t2 - t1
        print(f"total time num_workers:{num_workers}: time:{total_time}:")

        if total_time < best:
            # last_best = best_number
            best_number = num_workers
            best = total_time

        if num_workers - best_number > 1:
            # We tried to add more, but it didn't like it.
            #   so we stop with testing at this number.
            break

    return best_number


class WorkerQueue:
    def __init__(self, num_workers=20):
        self.queue = Queue()
        self.pool = []
        self._setup_workers(num_workers)

    def _setup_workers(self, num_workers):
        """Sets up the worker threads
        NOTE: undefined behaviour if you call this again.
        """
        self.pool = []

        for _ in range(num_workers):
            self.pool.append(Thread(target=self.threadloop))

        for a_thread in self.pool:
            a_thread.setDaemon(True)
            a_thread.start()

    def do(self, f, *args, **kwArgs):
        """puts a function on a queue for running later."""
        self.queue.put((f, args, kwArgs))

    def stop(self):
        """Stops the WorkerQueue, waits for all of the threads to finish up."""
        self.queue.put(STOP)
        for thread in self.pool:
            thread.join()

    def threadloop(self):  # , finish=False):
        """Loops until all of the tasks are finished."""
        while True:
            args = self.queue.get()
            if args is STOP:
                self.queue.put(STOP)
                self.queue.task_done()
                break
            try:
                args[0](*args[1], **args[2])
            finally:
                # clean up the queue, raise the exception.
                self.queue.task_done()
                # raise

    def wait(self):
        """waits until all tasks are complete."""
        self.queue.join()


class FuncResult:
    """Used for wrapping up a function call so that the results are stored
    inside the instances result attribute.
    """

    def __init__(self, f, callback=None, errback=None):
        """f - is the function we that we call
        callback(result) - this is called when the function(f) returns
        errback(exception) - this is called when the function(f) raises
                               an exception.
        """
        self.f = f
        self.exception = None
        self.result = None
        self.callback = callback
        self.errback = errback

    def __call__(self, *args, **kwargs):
        # we try to call the function here.  If it fails we store the exception.
        try:
            self.result = self.f(*args, **kwargs)
            if self.callback:
                self.callback(self.result)
        except Exception as e:
            self.exception = e
            if self.errback:
                self.errback(self.exception)


def tmap(f, seq_args, num_workers=20, worker_queue=None, wait=True, stop_on_error=True):
    """like map, but uses a thread pool to execute.
    num_workers - the number of worker threads that will be used.  If pool
                    is passed in, then the num_workers arg is ignored.
    worker_queue - you can optionally pass in an existing WorkerQueue.
    wait - True means that the results are returned when everything is finished.
           False means that we return the [worker_queue, results] right away instead.
           results, is returned as a list of FuncResult instances.
    stop_on_error -
    """

    if worker_queue:
        wq = worker_queue
    else:
        # see if we have a global queue to work with.
        if _wq:
            wq = _wq
        else:
            if num_workers == 0:
                return map(f, seq_args)

            wq = WorkerQueue(num_workers)

    # we short cut it here if the number of workers is 0.
    # normal map should be faster in this case.
    if len(wq.pool) == 0:
        return map(f, seq_args)

    # print("queue size:%s" % wq.queue.qsize())

    # TODO: divide the data (seq_args) into even chunks and
    #       then pass each thread a map(f, equal_part(seq_args))
    #      That way there should be less locking, and overhead.

    results = []
    for sa in seq_args:
        results.append(FuncResult(f))
        wq.do(results[-1], sa)

    # wq.stop()

    if wait:
        # print("wait")
        wq.wait()
        # print("after wait")
        # print("queue size:%s" % wq.queue.qsize())
        if wq.queue.qsize():
            raise RuntimeError("buggy threadmap")
        # if we created a worker queue, we need to stop it.
        if not worker_queue and not _wq:
            # print("stopping")
            wq.stop()
            if wq.queue.qsize():
                um = wq.queue.get()
                if not um is STOP:
                    raise RuntimeError("buggy threadmap")

        # see if there were any errors.  If so raise the first one.  This matches map behaviour.
        # TODO: the traceback doesn't show up nicely.
        # NOTE: TODO: we might want to return the results anyway?  This should be an option.
        if stop_on_error:
            error_ones = list(filter(lambda x: x.exception, results))
            if error_ones:
                raise error_ones[0].exception

        return map(lambda x: x.result, results)
    return [wq, results]
