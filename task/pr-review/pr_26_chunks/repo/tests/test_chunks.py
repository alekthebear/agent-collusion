from chunks import chunk_list


def test_even_split():
    assert chunk_list([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

def test_partial_last_chunk():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
