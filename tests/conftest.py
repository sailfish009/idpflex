from __future__ import print_function, absolute_import

import os
import sys
from copy import deepcopy

import pytest
import h5py
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
import MDAnalysis as mda

from idpflex import cnextend as cnx, properties as ps

# Resolve the path to the "external data"
this_module_path = sys.modules[__name__].__file__
data_dir = os.path.join(os.path.dirname(this_module_path), 'data')


@ps.decorate_as_node_property((('name',       'name of the property'),
                               ('domain_bar', 'property domain'),
                               ('bar',        'property_value'),
                               ('error_bar',  'property error')))
class SimpleProperty(object):
    """
    An integer property, only for testing purposes
    """
    def __init__(self, value=0):
        """
        :param value: integer value
        """
        self.name = 'foo'  # name of the simple property
        self.domain_bar = 0.0
        self.bar = int(value)  # value of the property
        self.error_bar = 0.0


@pytest.fixture(scope='session')
def small_tree():
    n_leafs = 9
    a = np.arange(n_leafs)
    dist_mat = squareform(np.square(a - a[:, np.newaxis]))
    z = linkage(dist_mat, method='complete')
    return {'dist_mat': dist_mat,
            'z': z,
            'tree': cnx.Tree(z),
            'simple_property': [SimpleProperty(i) for i in range(n_leafs)],
            }


@pytest.fixture(scope='session')
def benchmark():
    z = np.loadtxt(os.path.join(data_dir, 'linkage_matrix'))
    return {'z': z,
            'tree': cnx.Tree(z),
            'nnodes': 44757,
            'nleafs': 22379,
            'simple_property': [SimpleProperty(i) for i in range(22379)],
            }


@pytest.fixture(scope='session')
def trajectory_benchmark():
    r"""Load a trajectory into an MDAnalysis Universe instance

    Returns
    -------
    :class:`~MDAnalysis:MDAnalysis.core.universe.Universe`
    """
    sim_dir = os.path.join(data_dir, 'simulation')
    u = mda.Universe(os.path.join(sim_dir, 'hiAPP.pdb'))
    trajectory = os.path.join(sim_dir, 'hiAPP.xtc')
    u.load_new(trajectory)
    return u


@pytest.fixture(scope='session')
def saxs_benchmark():
    r"""Crysol output for one structure

    Returns
    ------
    dict
        'crysol_file': absolute path to file.
    """

    crysol_file = os.path.join(data_dir, 'saxs', 'crysol.dat')
    return dict(crysol_file=crysol_file)


@pytest.fixture(scope='session')
def sans_benchmark(request):
    r"""Sassena output containing 1000 I(Q) profiles for the hiAPP centroids.

    Yields
    ------
    dict
        'profiles' : HDF5 handle to the file containing the I(Q) profiles
        'property_list' : list of SansProperty instances, one for each leaf
        'tree_with_no_property' : cnextend.Tree with random distances among
            leafs and without included properties.
    """

    # setup or initialization
    handle = h5py.File(os.path.join(data_dir, 'sans', 'profiles.h5'), 'r')
    profiles = handle['fqt']
    n_leafs = len(profiles)

    # Create a node tree.
    # m is a 1D compressed matrix of distances between leafs
    m = np.random.random(int(n_leafs * (n_leafs - 1) / 2))
    Z = linkage(m)
    tree = cnx.Tree(Z)

    # values is a list of SansProperty instances, one for each tree leaf
    values = list()
    for i in range(tree.nleafs):
        sans_property = ps.SansProperty()
        sans_property.from_sassena(handle, index=i)
        values.append(sans_property)

    def teardown():
        handle.close()
    request.addfinalizer(teardown)
    return dict(profiles=handle, property_list=values,
                tree_with_no_property=tree)


@pytest.fixture(scope='session')
def sans_fit(sans_benchmark):
    r"""

    Parameters
    ----------
    sans_benchmark : pytest fixture

    Returns
    -------
    dict
        'tree': cnextend.Tree with random distances among leafs and endowed
            with a property.
        'experiment_property': SansProperty containing experimental profile
        'property_name':
        'depth': tree level giving the best fit to experiment
        'coefficients': weight of each cluster at tree level 'depth' after
            fitting.
    """
    tree = deepcopy(sans_benchmark['tree_with_no_property'])
    values = sans_benchmark['property_list']
    name = values[0].name  # property name
    ps.propagator_size_weighted_sum(values, tree)
    # create a SANS profile as a linear combination of the clusters at a
    # particular depth
    depth = 6
    coeff = (0.45, 0.00, 0.00, 0.10, 0.25, 0.00, 0.20)  # they must add to one
    clusters = tree.nodes_at_depth(depth)
    nclusters = 1 + depth  # depth=0 corresponds to the root node (nclusters=1)
    sans_property = clusters[0][name]
    profile = coeff[0] * sans_property.profile  # init with the first cluster
    flat_background = 0
    for i in range(1, nclusters):
        sans_property = clusters[i][name]
        profile += coeff[i] * sans_property.profile
        flat_background += np.mean(sans_property.profile)
    flat_background /= nclusters
    profile += flat_background  # add a flat background
    experiment_property = ps.ProfileProperty(qvalues=sans_property.qvalues,
                                             profile=profile,
                                             errors=0.1*profile)
    return {'tree': tree,
            'property_name': name,
            'depth': depth,
            'coefficients': coeff,
            'background': flat_background,
            'experiment_property': experiment_property}
