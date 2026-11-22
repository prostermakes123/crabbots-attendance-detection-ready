import numpy as np

from backend.app.services.gallery import FaceGallery


def test_gallery_matches_normalized_embedding():
    gallery = FaceGallery()
    vector = np.zeros(128, dtype=np.float32)
    vector[0] = 1.0
    gallery.add('member-1', 'CrabBot One', [vector])

    result = gallery.match(vector * 4, threshold=0.8, margin=0.05)

    assert result.accepted is True
    assert result.member_id == 'member-1'
    assert result.name == 'CrabBot One'
    assert result.similarity > 0.99


def test_gallery_rejects_invalid_dimensions_and_zero_vectors():
    gallery = FaceGallery()
    wrong_dimension = np.ones(64, dtype=np.float32)
    assert gallery.match(wrong_dimension, 0.4, 0.05).reason == 'dimension_mismatch'
    assert gallery.match(np.zeros(128, dtype=np.float32), 0.4, 0.05).reason == 'invalid_embedding'

    try:
        gallery.add('bad', 'Bad Vector', [wrong_dimension])
    except ValueError as exc:
        assert 'dimension mismatch' in str(exc)
    else:
        raise AssertionError('gallery.add should reject incompatible embedding dimensions')


def test_gallery_rejects_non_finite_embeddings():
    gallery = FaceGallery()
    vector = np.zeros(128, dtype=np.float32)
    vector[0] = np.nan
    assert gallery.match(vector, 0.4, 0.05).reason == 'invalid_embedding'
