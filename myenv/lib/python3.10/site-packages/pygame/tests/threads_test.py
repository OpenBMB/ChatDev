import unittest
from pygame.threads import FuncResult, tmap, WorkerQueue, Empty, STOP
from pygame import threads, Surface, transform


import time


class WorkerQueueTypeTest(unittest.TestCase):
    def test_usage_with_different_functions(self):
        def f(x):
            return x + 1

        def f2(x):
            return x + 2

        wq = WorkerQueue()
        fr = FuncResult(f)
        fr2 = FuncResult(f2)
        wq.do(fr, 1)
        wq.do(fr2, 1)
        wq.wait()
        wq.stop()

        self.assertEqual(fr.result, 2)
        self.assertEqual(fr2.result, 3)

    def test_do(self):
        """Tests function placement on queue and execution after blocking function completion."""
        # __doc__ (as of 2008-06-28) for pygame.threads.WorkerQueue.do:

        # puts a function on a queue for running _later_.

        # TODO: This tests needs refactoring to avoid sleep.
        #       sleep is slow and unreliable (especially on VMs).

        # def sleep_test():
        #     time.sleep(0.5)

        # def calc_test(x):
        #     return x + 1

        # worker_queue = WorkerQueue(num_workers=1)
        # sleep_return = FuncResult(sleep_test)
        # calc_return = FuncResult(calc_test)
        # init_time = time.time()
        # worker_queue.do(sleep_return)
        # worker_queue.do(calc_return, 1)
        # worker_queue.wait()
        # worker_queue.stop()
        # time_diff = time.time() - init_time

        # self.assertEqual(sleep_return.result, None)
        # self.assertEqual(calc_return.result, 2)
        # self.assertGreaterEqual(time_diff, 0.5)

    def test_stop(self):
        """Ensure stop() stops the worker queue"""
        wq = WorkerQueue()

        self.assertGreater(len(wq.pool), 0)

        for t in wq.pool:
            self.assertTrue(t.is_alive())

        for i in range(200):
            wq.do(lambda x: x + 1, i)

        wq.stop()

        for t in wq.pool:
            self.assertFalse(t.is_alive())

        self.assertIs(wq.queue.get(), STOP)

    def test_threadloop(self):
        # __doc__ (as of 2008-06-28) for pygame.threads.WorkerQueue.threadloop:

        # Loops until all of the tasks are finished.

        # Make a worker queue with only one thread
        wq = WorkerQueue(1)

        # Ocuppy the one worker with the threadloop
        # wq threads are just threadloop, so this makes an embedded threadloop
        wq.do(wq.threadloop)

        # Make sure wq can still do work
        # If wq can still do work, threadloop works
        l = []
        wq.do(l.append, 1)
        # Wait won't work because the primary thread is in an infinite loop
        time.sleep(0.5)
        self.assertEqual(l[0], 1)

        # Kill the embedded threadloop by sending stop onto the stack
        # Threadloop puts STOP back onto the queue when it STOPs so this kills both loops
        wq.stop()

        # Make sure wq has stopped
        self.assertFalse(wq.pool[0].is_alive())

    def test_wait(self):
        # __doc__ (as of 2008-06-28) for pygame.threads.WorkerQueue.wait:

        # waits until all tasks are complete.

        wq = WorkerQueue()

        for i in range(2000):
            wq.do(lambda x: x + 1, i)
        wq.wait()

        self.assertRaises(Empty, wq.queue.get_nowait)

        wq.stop()


class ThreadsModuleTest(unittest.TestCase):
    def test_benchmark_workers(self):
        """Ensure benchmark_workers performance measure functions properly with both default and specified inputs"""
        "tags:long_running"

        # __doc__ (as of 2008-06-28) for pygame.threads.benchmark_workers:

        # does a little test to see if workers are at all faster.
        # Returns the number of workers which works best.
        # Takes a little bit of time to run, so you should only really call
        #   it once.
        # You can pass in benchmark data, and functions if you want.
        # a_bench_func - f(data)
        # the_data - data to work on.
        optimal_workers = threads.benchmark_workers()
        self.assertIsInstance(optimal_workers, int)
        self.assertTrue(0 <= optimal_workers < 64)

        # Test passing benchmark data and function explicitly
        def smooth_scale_bench(data):
            transform.smoothscale(data, (128, 128))

        surf_data = [Surface((x, x), 0, 32) for x in range(12, 64, 12)]
        best_num_workers = threads.benchmark_workers(smooth_scale_bench, surf_data)
        self.assertIsInstance(best_num_workers, int)

    def test_init(self):
        """Ensure init() sets up the worker queue"""
        threads.init(8)

        self.assertIsInstance(threads._wq, WorkerQueue)

        threads.quit()

    def test_quit(self):
        """Ensure quit() cleans up the worker queue"""
        threads.init(8)
        threads.quit()

        self.assertIsNone(threads._wq)

    def test_tmap(self):
        # __doc__ (as of 2008-06-28) for pygame.threads.tmap:

        # like map, but uses a thread pool to execute.
        # num_workers - the number of worker threads that will be used.  If pool
        #                 is passed in, then the num_workers arg is ignored.
        # worker_queue - you can optionally pass in an existing WorkerQueue.
        # wait - True means that the results are returned when everything is finished.
        #        False means that we return the [worker_queue, results] right away instead.
        #        results, is returned as a list of FuncResult instances.
        # stop_on_error -

        ## test that the outcomes of map and tmap are the same
        func, data = lambda x: x + 1, range(100)

        tmapped = list(tmap(func, data))
        mapped = list(map(func, data))

        self.assertEqual(tmapped, mapped)

        ## Test that setting tmap to not stop on errors produces the expected result
        data2 = range(100)
        always_excepts = lambda x: 1 / 0

        tmapped2 = list(tmap(always_excepts, data2, stop_on_error=False))

        # Use list comprehension to check all entries are None as all function
        # calls made by tmap will have thrown an exception (ZeroDivisionError)
        # Condense to single bool with `all`, which will return true if all
        # entries are true
        self.assertTrue(all([x is None for x in tmapped2]))

    def todo_test_tmap__None_func_and_multiple_sequences(self):
        """Using a None as func and multiple sequences"""
        self.fail()

        res = tmap(None, [1, 2, 3, 4])
        res2 = tmap(None, [1, 2, 3, 4], [22, 33, 44, 55])
        res3 = tmap(None, [1, 2, 3, 4], [22, 33, 44, 55, 66])
        res4 = tmap(None, [1, 2, 3, 4, 5], [22, 33, 44, 55])

        self.assertEqual([1, 2, 3, 4], res)
        self.assertEqual([(1, 22), (2, 33), (3, 44), (4, 55)], res2)
        self.assertEqual([(1, 22), (2, 33), (3, 44), (4, 55), (None, 66)], res3)
        self.assertEqual([(1, 22), (2, 33), (3, 44), (4, 55), (5, None)], res4)

    def test_tmap__wait(self):
        r = range(1000)
        wq, results = tmap(lambda x: x, r, num_workers=5, wait=False)
        wq.wait()
        r2 = map(lambda x: x.result, results)
        self.assertEqual(list(r), list(r2))

    def test_FuncResult(self):
        """Ensure FuncResult sets its result and exception attributes"""
        # Results are stored in result attribute
        fr = FuncResult(lambda x: x + 1)
        fr(2)

        self.assertEqual(fr.result, 3)

        # Exceptions are store in exception attribute
        self.assertIsNone(fr.exception, "no exception should be raised")

        exception = ValueError("rast")

        def x(sdf):
            raise exception

        fr = FuncResult(x)
        fr(None)

        self.assertIs(fr.exception, exception)


################################################################################

if __name__ == "__main__":
    unittest.main()
