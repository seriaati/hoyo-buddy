from typing import List, TypeVar

T = TypeVar("T")


def split_list(input_list: List[T], n: int) -> List[List[T]]:
    """
    Split a list into sublists of length n

    Parameters:
        input_list: The input list
        n: The length of each sublist
    """
    if n <= 0:
        raise ValueError("Parameter n must be a positive integer")

    return [input_list[i : i + n] for i in range(0, len(input_list), n)]
