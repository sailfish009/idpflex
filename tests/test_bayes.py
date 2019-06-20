import numpy as np
from numpy.testing import assert_array_almost_equal, assert_array_equal
import pytest

from idpflex import bayes
from idpflex import properties


def test_model_at_node(sans_fit):
    tree = sans_fit['tree']
    mod = bayes.model_at_node(tree.root, sans_fit['property_name'])
    prop = tree.root[sans_fit['property_name']]
    params = mod.make_params()
    assert_array_almost_equal(mod.eval(params, x=prop.qvalues),
                              prop.y, decimal=1)


def test_model_at_depth(sans_fit):
    tree = sans_fit['tree']
    name = sans_fit['property_name']
    depth = sans_fit['depth']
    # Evaluate the model
    mod = bayes.model_at_depth(tree, depth, name)
    params = mod.make_params()
    for id, coeff in sans_fit['coefficients'].items():
        params['n{}_amplitude'.format(id)].set(value=coeff)
    params['c'].set(value=sans_fit['background'])
    p_exp = sans_fit['experiment_property']
    assert_array_almost_equal(mod.eval(params, x=p_exp.x),
                              p_exp.y, decimal=1)


def test_fit_at_depth(sans_fit):
    tree = sans_fit['tree']
    name = sans_fit['property_name']
    p_exp = sans_fit['experiment_property']
    fit = bayes.fit_at_depth(tree, p_exp, name, sans_fit['depth'])
    assert fit.chisqr < 1e-10


def test_fit_to_depth(sans_fit):
    tree = sans_fit['tree']
    name = sans_fit['property_name']
    p_exp = sans_fit['experiment_property']
    fits = bayes.fit_to_depth(tree, p_exp, name, max_depth=7)
    chi2 = np.asarray([fit.chisqr for fit in fits])
    assert np.argmax(chi2 < 1e-10) == sans_fit['depth']


def test_fit_at_depth_multi(sans_fit):
    tree = sans_fit['tree']
    exp = sans_fit['experiment_property']
    exp_pd = properties.PropertyDict([exp])
    mod = bayes.create_at_depth_multiproperty(tree, sans_fit['depth'])
    fit = bayes.fit_multiproperty_model(mod, exp_pd)
    assert fit.weights is None
    assert fit.chisqr < 1e-10
    fit2 = bayes.fit_multiproperty_model(mod, exp_pd,
                                         weights=exp_pd.feature_weights)
    assert_array_equal(fit2.weights, exp_pd.feature_weights)


def test_fit_to_depth_multi(sans_fit):
    tree = sans_fit['tree']
    exp = sans_fit['experiment_property']
    exp_pd = properties.PropertyDict([exp])
    mods = bayes.create_to_depth_multiproperty(tree, max_depth=7)
    fits = bayes.fit_multiproperty_models(mods, exp_pd)
    chi2 = np.array([fit.chisqr for fit in fits])
    assert np.argmax(chi2 < 1e-10) == sans_fit['depth']


def test_multiproperty_fit(sans_fit):
    tree = sans_fit['tree']
    exp = sans_fit['experiment_property']
    scalar = properties.ScalarProperty(name='foo', x=1, y=1, e=1)
    values = [properties.ScalarProperty(name='foo', x=1, y=i, e=1)
              for i in range(len(tree.leafs))]
    properties.propagator_size_weighted_sum(values, tree)
    exp_pd = properties.PropertyDict([exp, scalar])
    models = bayes.create_to_depth_multiproperty(tree, max_depth=7)
    fits = bayes.fit_multiproperty_models(models, exp_pd)
    chi2 = np.array([fit.chisqr for fit in fits])
    assert 'const_foo' not in fits[0].best_values.keys()
    assert np.argmax(chi2 < 1e-10) == sans_fit['depth']


def test_fit_bad_input(sans_fit):
    tree = sans_fit['tree']
    exp = sans_fit['experiment_property']
    name = sans_fit['property_name']
    scalar = properties.ScalarProperty(name='foo', x=1, y=1, e=1)
    # Different x value to prompt error
    values = [properties.ScalarProperty(name='foo', x=10, y=i, e=1)
              for i in range(len(tree.leafs))]
    properties.propagator_size_weighted_sum(values, tree)
    exp_pd = properties.PropertyDict([exp, scalar])
    with pytest.raises(ValueError):
        models = bayes.create_to_depth_multiproperty(tree, max_depth=7)
        bayes.fit_multiproperty_models(models, exp_pd)
    with pytest.raises(ValueError):
        mods = bayes.create_to_depth_multiproperty(tree, max_depth=7)
        bayes.fit_multiproperty_models(mods, exp_pd.subset([name]))
    with pytest.raises(ValueError):
        left_child = tree.root.get_left()
        left_child.property_group = left_child.property_group.subset([name])
        mods = bayes.create_to_depth_multiproperty(tree, max_depth=7)
        bayes.fit_multiproperty_models(mods, exp_pd)

    p_exp = sans_fit['experiment_property']
    with pytest.raises(ValueError):
        p_exp.x += 1
        bayes.fit_at_depth(tree, p_exp, name, sans_fit['depth'])


if __name__ == '__main__':
    pytest.main()
