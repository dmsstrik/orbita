"""Isolated worker processes for graph computations."""

from __future__ import annotations

import multiprocessing as mp
import threading

_slots = threading.BoundedSemaphore(2)


class JobTimeout(TimeoutError):
    pass


class JobBusy(RuntimeError):
    pass


def _worker(connection, operation: str, arguments: tuple):
    try:
        if operation == "analyze":
            from .analysis import analyze_graph
            result = analyze_graph(*arguments)
        elif operation == "experiments":
            from .experiments import run_experiments
            result = run_experiments(*arguments)
        elif operation == "vk":
            from .vk import fetch_vk_graph
            result = fetch_vk_graph(*arguments)
        else:
            raise ValueError("Неизвестная операция.")
        connection.send((True, result))
    except ValueError as error:
        connection.send((False, str(error)))
    except Exception:
        # Exception details may contain tokens or file paths.
        connection.send((False, "Не удалось завершить расчёт. Проверьте входные данные и повторите запрос."))
    finally:
        connection.close()


def run_job(operation: str, *arguments, timeout: float = 30):
    if not _slots.acquire(blocking=False):
        raise JobBusy("Уже выполняются два расчёта. Дождитесь завершения и повторите запрос.")
    process = None
    parent = child = None
    try:
        context = mp.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_worker, args=(child, operation, arguments), daemon=True)
        process.start()
        child.close()
        if not parent.poll(timeout):
            raise JobTimeout("Превышено время расчёта. Уменьшите граф или число повторов эксперимента.")
        try:
            success, result = parent.recv()
        except EOFError as exc:
            raise ValueError("Вычислительный процесс завершился без результата. Попробуйте меньший граф.") from exc
        if not success:
            raise ValueError(result)
        return result
    finally:
        if process is not None and process.pid is not None:
            process.join(timeout=0.3)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            process.close()
        if parent is not None:
            parent.close()
        if child is not None:
            child.close()
        _slots.release()
