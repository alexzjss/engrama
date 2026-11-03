from engrama import vocab


def test_branches_shape():
    assert len(vocab.BRANCH_STAGES) == 4
    for stage in vocab.BRANCH_STAGES:
        ids = vocab.BRANCHES[stage]
        assert 4 <= len(ids) <= 5
        assert len([b for b in ids if b in vocab.NEGLECT_BRANCHES]) == 1
        for b in ids:
            assert b.isascii()


def test_interest_groups_values_in_keys():
    assert set(vocab.INTEREST_GROUPS.values()) <= set(vocab.INTEREST_KEYS)


def test_medicine_not_a_food():
    assert vocab.MEDICINE_ID not in vocab.FOOD_IDS
