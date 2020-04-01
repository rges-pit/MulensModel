import warnings
import numpy as np
from math import log, fsum

from matplotlib import rcParams
import matplotlib.pyplot as plt

from astropy.coordinates import SkyCoord
import astropy.units as u

from MulensModel.utils import Utils
from MulensModel.fitdata import FitData
from MulensModel.mulensdata import MulensData
from MulensModel.model import Model
from MulensModel.coordinates import Coordinates
from MulensModel.trajectory import Trajectory
from MulensModel import mm_plot


class Event(object):
    """
    Combines a microlensing model with data. Allows calculating chi^2 and
    making a number of plots.

    Arguments :
        :py:obj:`~datasets` :  :py:class:`~MulensModel.mulensdata.MulensData`
        or *list* of :py:class:`~MulensModel.mulensdata.MulensData` objects
            Datasets that will be linked to the event. These datasets will
            be used for chi^2 calculation, plotting etc.

        :py:obj:`~model` : :py:class:`~MulensModel.model.Model`
            Microlensing model that will be linked to the event. In order to
            get chi^2 for different sets of model parameters you should
            keep a single :py:class:`~MulensModel.model.Model` instance and
            change parameters for this model (i.e., do not provide separate
            :py:class:`~MulensModel.model.Model` instances).

        :py:obj:`~coords` : *str*,
        :py:class:`~MulensModel.coordinates.Coordinates`, or astropy.SkyCoord_
            Coordinates of the event. If *str*, then needs format accepted by
            astropy.SkyCoord_ e.g., ``'18:00:00 -30:00:00'``.

        fix_blend_flux, fix_source_flux: *dict*
            Used to fix the source flux(es) or blend flux
            (q_flux for 1L2S models) for a particular dataset. The dataset is
            the key, and the value to be fixed is the value. For example, to
            fix the blending of some dataset *my_data* to zero set
            *fix_blend_flux={my_data: 0.}*. See also
            :py:class:`~MulensModel.fitdata.FitData` .

        fix_q_flux: *dict*
            Used to fix the flux ratio for a given band or dataset. The keys
            should be either :py:class:`~MulensModel.mulensdata.MulensData`
            objects or *str*. If a
            :py:class:`~MulensModel.mulensdata.MulensData` object is specified,
            it will take precedence over a band.

        fit: :py:class:`~MulensModel.fit.Fit` or *None*
            Instance of :py:class:`~MulensModel.fit.Fit` class used in
            the last calculation of chi^2 or its gradient. In can be used to
            extract source and bleding fluxes. If no chi^2 calculation was
            performed, then it is *None*.

        data_ref: *int* or :py:class:`~MulensModel.mulensdata.MulensData`
            Reference dataset. If *int* then gives index of reference dataset
            in :py:attr:`~datasets`. Default is the first dataset.

    The datasets can be in magnitude or flux spaces. When we calculate chi^2
    we do it in magnitude or flux space depending on value of
    :py:attr:`~MulensModel.mulensdata.MulensData.chi2_fmt` attribute.
    If dataset is in magnitude space and model results
    in negative flux, then we calculate chi^2 in flux space but only for the
    epochs with negative model flux.

    .. _astropy.SkyCoord:
      http://docs.astropy.org/en/stable/api/astropy.coordinates.SkyCoord.html
    """

    def __init__(
            self, datasets=None, model=None, coords=None, fix_blend_flux={},
            fix_source_flux={}, fix_q_flux={}, data_ref=0):
        self._model = None
        self._coords = None

        # Initialize self._model (and check that model is defined).
        if isinstance(model, Model):
            self._model = model
        elif model is not None:
            raise TypeError('incorrect argument model of class Event()')

        # Initialize self._datasets (and check that datasets is defined).
        if isinstance(datasets, (list, tuple, MulensData)) or datasets is None:
            self._set_datasets(datasets)
        else:
            raise TypeError('incorrect argument datasets of class Event()')

        self._data_ref = self._set_data_ref(data_ref)

        # Set event coordinates
        if coords is not None:
            self._update_coords(coords=coords)
        elif self._model is not None:
            if self._model.coords is not None:
                self._update_coords(coords=self._model.coords)

        self.reset_best_chi2()  # To be deprecated
        self.sum_function = 'math.fsum'
        self.fit = None  # This should be changed to @property w/ lazy loading

        # New Stuff related to Fit Data
        self.fits = None  # New property
        self.chi2 = None
        self.fix_blend_flux = fix_blend_flux
        self.fix_source_flux = fix_source_flux
        self.fix_q_flux = fix_q_flux

    def plot_model(self, data_ref=None, **kwargs):
        """
        Plot the model light curve in magnitudes. See
        :py:func:`MulensModel.model.Model.plot_lc()` for details.

        Keywords :
            data_ref: *int* or *MulensData*
                If data_ref is not specified, uses :py:obj:`~data_ref`.

        """
        if data_ref is None:
            data_ref = self.data_ref

        (f_source_0, f_blend_0) = self.get_flux_for_dataset(data_ref)
        self.model.plot_lc(f_source=f_source_0, f_blend=f_blend_0, **kwargs)

    def plot_data(
            self, phot_fmt='mag', data_ref=None, show_errorbars=None,
            show_bad=None,
            color_list=None, marker_list=None, size_list=None,
            label_list=None, alpha_list=None, zorder_list=None,
            subtract_2450000=False, subtract_2460000=False, **kwargs):
        """
        Plot the data scaled to the model.

        Keywords (all optional):
            phot_fmt: *string* ('mag', 'flux')
                Whether to plot the data in magnitudes or in flux. Default
                is 'mag'.

            data_ref: *int* or *MulensData*
                If data_ref is not specified, uses :py:obj:`~data_ref`.

            show_errorbars: *boolean* or *None*
                Do you want errorbars to be shown for all datasets?
                Default is *None*, which means the option is taken from each
                dataset plotting properties (for which default is *True*).
                If *True*, then data are plotted using matplotlib.errorbar().
                If *False*, then data are plotted using matplotlib.scatter().

            show_bad: *boolean* or *None*
                Do you want data marked as bad to be shown?
                Default is *None*, which means the option is taken from each
                dataset plotting properties (for which default is *False*).
                If bad data are shown, then they are plotted with 'x' marker.

            subtract_2450000, subtract_2460000: *boolean*
                If True, subtracts 2450000 or 2460000 from the time
                axis to get more human-scale numbers. If using, make
                sure to also set the same settings for all other
                plotting calls (e.g. :py:func:`plot_lc()`).

            ``**kwargs``:
                Passed to matplotlib plotting functions. Contrary to
                previous behavior, ``**kwargs`` are no longer remembered.

        """
        # Officially deprecating
        # self._check_old_plot_kwargs(
        #     color_list=color_list, marker_list=marker_list,
        #     size_list=size_list, label_list=label_list,
        #     alpha_list=alpha_list, zorder_list=zorder_list)

        self._set_default_colors()  # For each dataset
        if self.fits is None:
            self.get_chi2()

        if data_ref is None:
            data_ref = self.data_ref

        # JCY want to implement show_errobars, show_bad as list option, so it
        # can be different for different datasets. DO LATER.

        # Set plot limits
        t_min = 3000000.
        t_max = 0.
        subtract = mm_plot.subtract(subtract_2450000, subtract_2460000)

        # Get fluxes for all datasets
        # if self.model.n_sources > 1:
        #     raise NotImplementedError(
        #         'Scaling data to model not implemented for multiple sources.')

        (f_source_0, f_blend_0) = self.get_flux_for_dataset(data_ref)
        for (i, data) in enumerate(self._datasets):
            # Get the fitted fluxes
            # (f_source, f_blend) = self.get_flux_for_dataset(i)

            # Scale the data flux
            # flux = f_source_0 * (data.flux - f_blend) / f_source
            # flux += f_blend_0
            # err_flux = f_source_0 * data.err_flux / f_source
            (flux, err_flux) = self.fits[i].scale_fluxes(f_source_0, f_blend_0)
            (y_value, y_err) = mm_plot._get_y_value_y_err(
                phot_fmt, flux, err_flux)

            data._plot_datapoints(
                (y_value, y_err), subtract_2450000=subtract_2450000,
                subtract_2460000=subtract_2460000,
                show_errorbars=show_errorbars, show_bad=show_bad, **kwargs)

            t_min = min(t_min, np.min(data.time))
            t_max = max(t_max, np.max(data.time))

        # Plot properties
        plt.ylabel('Magnitude')
        plt.xlabel(
            mm_plot._subtract_xlabel(subtract_2450000, subtract_2460000))
        plt.xlim(t_min-subtract, t_max-subtract)

        (ymin, ymax) = plt.gca().get_ylim()
        if ymax > ymin:
            plt.gca().invert_yaxis()

    def plot_residuals(self, show_errorbars=None,
            data_ref=None, subtract_2450000=False, subtract_2460000=False,
            show_bad=None, **kwargs):
        """
        Plot the residuals (in magnitudes) to the model.

                For explanation of keywords, see doctrings in
        :py:func:`plot_data()`. Note different order of keywords.
        """
        self._set_default_colors()

        if data_ref is None:
            data_ref = self.data_ref

        # Plot limit parameters
        t_min = 3000000.
        t_max = 0.
        subtract = mm_plot.subtract(subtract_2450000, subtract_2460000)

        # Plot zeropoint line
        plt.plot([0., 3000000.], [0., 0.], color='black')

        # Plot residuals
        (f_source_0, f_blend_0) = self.get_flux_for_dataset(data_ref)
        for i, data in enumerate(self._datasets):
            (residuals, errorbars)  = self.fits[i].get_residuals(
                phot_fmt='scaled', source_flux=f_source_0, blend_flux=f_blend_0)
            y_value = residuals
            y_err = errorbars
            data._plot_datapoints(
                (y_value, y_err), subtract_2450000=subtract_2450000,
                subtract_2460000=subtract_2460000,
                show_errorbars=show_errorbars, show_bad=show_bad, **kwargs)

            t_min = min(t_min, np.min(data.time))
            t_max = max(t_max, np.max(data.time))

        # Plot properties
        y_lim = np.max([np.abs(y_lim) for y_lim in plt.gca().get_ylim()])
        if y_lim > 1.:
            y_lim = 0.5

        plt.ylim(y_lim, -y_lim)
        plt.xlim(t_min-subtract, t_max-subtract)
        plt.ylabel('Residuals')
        plt.xlabel(mm_plot._subtract_xlabel(subtract_2450000, subtract_2460000))

    def plot_trajectory(self, **kwargs):
        """
        Plot the trajectory of the source. See :
        py:func:`MulensModel.model.Model.plot_trajectory()` for details.
        """
        self.model.plot_trajectory(**kwargs)

    def plot_source_for_datasets(self, **kwargs):
        """
        Plot source positions for all linked datasets.
        See :py:func:`MulensModel.model.Model.plot_source_for_datasets()` for
        details.
        """
        pass
        # self.model.plot_source_for_datasets(**kwargs)

    def _set_default_colors(self):
        """
        If the user has not specified a color for a dataset, assign
        one.
        """
        # JCY --> plot_functions.py?
        colors = [cycle['color'] for cycle in rcParams['axes.prop_cycle']]

        # Below we change the order of colors to most distinct first.
        used_colors = []
        for data in self._datasets:
            if 'color' in data.plot_properties.keys():
                used_colors.append(data.plot_properties['color'])

        if len(used_colors) == len(self._datasets):
            return

        if len(used_colors) == 0:
            differences = None
        else:
            d_col = self._color_differences
            diffs = np.array([np.min(d_col(used_colors, c)) for c in colors])
            indexes = np.argsort(diffs)[::-1]
            colors = [colors[i] for i in indexes]
            differences = diffs[indexes]

        # Assign colors when needed.
        color_index = 0
        for data in self._datasets:
            if 'color' not in data.plot_properties.keys():
                if differences is not None:
                    if differences[color_index] < 0.35:
                        msg = ('The color assign to one of the datasets in ' +
                               'automated way (' + colors[color_index] +
                               ') is very similar to already used color')
                        warnings.warn(msg, UserWarning)

                data.plot_properties['color'] = colors[color_index]
                color_index += 1
                if color_index == len(colors):
                    color_index = 0
                    msg = ('Too many datasets without colors assigned - ' +
                           'same color will be used for different datasets')
                    warnings.warn(msg, UserWarning)

    def get_flux_for_dataset(self, dataset):
        """
        Get the source and blend flux for a given dataset.

        Parameters :
            dataset: :py:class:`~MulensModel.mulensdata.MulensData` or *int*
            If *int* should be the index (starting at 0) of the appropriate
            dataset in the :py:obj:`~datasets` list.

        Returns :
            f_source: *np.ndarray*
                Sources' flux; normally of size (1). If it is of size (1)
                for a double source model, then it is a sum of fluxes
                of both sources.
            f_blend: *float*
                blending flux

        NOTE: This function does not recalculate fits or fluxes. If the data
        haven't yet been fit to the model (i.e. self.fits = None),
        it will run :py:func:`~fit_fluxes()`. Otherwise, it just accesses the
        existing values. So if you change something in :py:obj:`~model` or
        some fit parameter (e.g., :py:obj:`~fix_blending`), be sure to run
        :py:func:`~fit_fluxes()` first.

        """
        # JCY - This entire method is new and does *not* have unit tests.
        if self.fits is None:
            self.fit_fluxes()

        if isinstance(dataset, MulensData):
            i = np.where(self.datasets == dataset)
        else:
            i = dataset

        f_source = self.fits[i].source_fluxes
        f_blend = self.fits[i].blend_flux

        return (f_source, f_blend)

    def get_ref_fluxes(self, data_ref=None, fit_blending=None):
        """
        Get source and blending fluxes for the reference dataset. See
        :py:func:`~get_flux_for_dataset()`. If the reference dataset is not
        set, uses the first dataset as default. See :py:obj:`~data_ref`.
        """
        if data_ref is not None:
            warnings.warn(
                'data_ref will be deprecated. It is redundant for getting ' +
                'the flux of the reference dataset. For the flux of an ' +
                'arbitrary dataset, use get_flux_for_dataset')

        if fit_blending is not None:
            self._apply_fit_blending(fit_blending)

        return self.get_flux_for_dataset(self.data_ref)

    def get_chi2(self, fit_blending=None):
        """
        Calculates chi^2 of current model by fitting for source and
        blending fluxes.

        Parameters :
            fit_blending: *boolean*, optional
                If *True*, then the blend flux is a free parameter. If
                *False*, the blend flux is fixed at zero.  Default is
                the same as :py:func:`MulensModel.fit.Fit.fit_fluxes()`.

        Returns :
            chi2: *float*
                Chi^2 value

        """
        if fit_blending is not None:
            self._apply_fit_blending(fit_blending)

        self.fit_fluxes()
        chi2 = []
        for (i, dataset) in enumerate(self.datasets):
            # Calculate chi2 for the dataset excluding bad data
            chi2.append(self.fits[i].chi2)

        self.chi2 = self._sum(chi2)

        # To be deprecated
        if self._best_chi2 is None or self._best_chi2 > self.chi2:
            self._best_chi2 = self.chi2
            self._best_chi2_parameters = dict(self.model.parameters.parameters)

        return self.chi2

        # chi2_per_point = self.get_chi2_per_point(
        #     fit_blending=fit_blending)
        # # Calculate chi^2 given the fit
        # chi2 = []
        # for (i, dataset) in enumerate(self.datasets):
        #     # Calculate chi2 for the dataset excluding bad data
        #     chi2.append(self._sum(chi2_per_point[i][dataset.good]))
        #
        # self.chi2 = self._sum(chi2)
        # if self.best_chi2 is None or self.best_chi2 > self.chi2:
        #     self._best_chi2 = self.chi2
        #     self._best_chi2_parameters = dict(self.model.parameters.parameters)
        # return self.chi2

    def get_chi2_for_dataset(self, index_dataset, fit_blending=None):
        """
        Calculates chi^2 for a single dataset

        Parameters :
            index_dataset: *int*
                index that specifies for which dataset the chi^2 is requested

            fit_blending: *boolean*, optional
                Are we fitting for blending flux? If not then blending flux is
                fixed to 0.  Default is the same as
                :py:func:`MulensModel.fit.Fit.fit_fluxes()`.

        Returns :
            chi2: *float*
                chi2 for dataset[index_dataset].

        """
        if fit_blending is not None:
            self._apply_fit_blending(fit_blending)

        self.fit_fluxes()

        return self.fits[index_dataset].chi2

        # if self.model.n_sources > 1 and fit_blending is False:
        #     raise NotImplementedError("Sorry, chi2 for binary sources with " +
        #                               "no blending is not yet coded.")
        # if not isinstance(index_dataset, int):
        #     msg = 'index_dataset has to be int type, not {:}'
        #     raise TypeError(msg.format(type(index_dataset)))
        #
        # dataset = self.datasets[index_dataset]
        # magnification = self.model.get_data_magnification(dataset)
        #
        # dataset_in_fit = True
        # if self.model.fit is None:
        #     dataset_in_fit = False
        # else:
        #     try:
        #         self.model.fit.flux_of_sources(dataset)
        #     except KeyError:
        #         dataset_in_fit = False
        # if self.model.n_sources != 1 and dataset_in_fit:
        #     self.fit = self.model.fit
        # else:
        #     self._update_data_in_model()
        #     self.fit = Fit(data=dataset, magnification=[magnification])
        #     if fit_blending is not None:
        #         self.fit.fit_fluxes(fit_blending=fit_blending)
        #     else:
        #         self.fit.fit_fluxes()
        #
        # (data, err_data) = dataset.data_and_err_in_chi2_fmt()
        #
        # model = self.fit.get_chi2_format(data=dataset)
        # diff = data - model
        # if np.any(np.isnan(model[dataset.good])):  # This can happen only for
        #     # input_fmt = 'mag' and model flux < 0.
        #     mask = np.isnan(model)
        #     masked_model = self.fit.get_flux(data=dataset)[mask]
        #     diff[mask] = dataset.flux[mask] - masked_model
        #     err_data[mask] = dataset.err_flux[mask]
        # chi2 = (diff / err_data) ** 2
        # return self._sum(chi2[dataset.good])

    def get_chi2_per_point(self, fit_blending=None):
        """
        Calculates chi^2 for each data point of the current model by
        fitting for source and blending fluxes.

        Parameters :
            fit_blending: *boolean*, optional
                Are we fitting for blending flux? If not then blending flux is
                fixed to 0.  Default is the same as
                :py:func:`MulensModel.fit.Fit.fit_fluxes()`.

        Returns :
            chi2: *list* of *np.ndarray*
                Chi^2 contribution from each data point,
                e.g. ``chi2[data_num][k]`` returns the chi2 contribution
                from the *k*-th point of dataset *data_num*.

        Example :
            Assuming ``event`` is instance of Event class to get chi2
            for 10-th point point of 0-th dataset.

            .. code-block:: python

               chi2 = event.get_chi2_per_point()
               print(chi2[0][10])

        """
        # JCY - This function does not seem to be covered by unit tests.
        if fit_blending is not None:
            self._apply_fit_blending(fit_blending)

        self.fit_fluxes()

        # Calculate chi^2 given the fit
        chi2_per_point = []
        for (i, dataset) in enumerate(self.datasets):
            chi2_per_point.append(self.fits[i].chi2_per_point)

        return chi2_per_point
        # if self.model.n_sources > 1 and fit_blending is False:
        #     raise NotImplementedError("Sorry, chi2 for binary sources with " +
        #                               "no blending is not yet coded.")
        #
        # # Define a Fit given the model and perform linear fit for fs and fb
        # if (self.model.n_sources != 1 and
        #         self.model._source_flux_ratio_constraint is None):
        #     self.model.data_magnification
        #     self.fit = self.model.fit
        # else:
        #     self._update_data_in_model()
        #     self.fit = Fit(data=self.datasets,
        #                    magnification=self.model.data_magnification)
        #     if fit_blending is not None:
        #         self.fit.fit_fluxes(fit_blending=fit_blending)
        #     else:
        #         self.fit.fit_fluxes()
        #
        # # Calculate chi^2 given the fit
        # chi2_per_point = []
        # for (i, dataset) in enumerate(self.datasets):
        #     if dataset.chi2_fmt == "mag":
        #         data = dataset.mag
        #         err_data = dataset.err_mag
        #     elif dataset.chi2_fmt == "flux":
        #         data = dataset.flux
        #         err_data = dataset.err_flux
        #     else:
        #         raise ValueError('Unrecognized data format: {:}'.format(
        #             dataset.chi2_fmt))
        #     model = self.fit.get_chi2_format(data=dataset)
        #     diff = data - model
        #     if np.any(np.isnan(model)):  # This can happen only for
        #         # input_fmt = 'mag' and model flux < 0.
        #         mask = np.isnan(model)
        #         masked_model = self.fit.get_flux(data=dataset)[mask]
        #         diff[mask] = dataset.flux[mask] - masked_model
        #         err_data[mask] = dataset.err_flux[mask]
        #
        #     chi2_per_point.append((diff / err_data) ** 2)
        #
        # return chi2_per_point

    def get_chi2_gradient(self, parameters):
        """ Same as :py:func:`~chi2_gradient except it fits for the fluxes
        first."""
        self.fit_fluxes()
        return self. chi2_gradient(parameters)

    def chi2_gradient(self, parameters, fit_blending=None):
        """
        Calculate chi^2 gradient (also called Jacobian), i.e.,
        :math:`d chi^2/d parameter`.

        Parameters :
            parameters: *str* or *list*, required
                Parameters with respect to which gradient is calculated.
                Currently accepted parameters are: ``t_0``, ``u_0``, ``t_eff``,
                ``t_E``, ``pi_E_N``, and ``pi_E_E``. The parameters for
                which you request gradient must be defined in py:attr:`~model`.

            fit_blending: *boolean*, optional
                Are we fitting for blending flux? If not then blending flux is
                fixed to 0.  Default is the same as
                :py:func:`MulensModel.fit.Fit.fit_fluxes()`.

        Returns :
            gradient: *float* or *np.ndarray*
                chi^2 gradient

        NOTE: Because this is not a 'get' function, it ASSUMES you have ALREADY
        fit for the fluxes, e.g. by calling get_chi2().
        """
        if fit_blending is not None:
            self._apply_fit_blending(fit_blending)

        gradient = {param: 0 for param in parameters}
        for i, dataset in enumerate(self.datasets):
            data_gradient = self.fits[i].chi2_gradient(parameters)
            for i, p in enumerate(parameters):
                gradient[p] += data_gradient[i]

        # if not isinstance(parameters, list):
        #     parameters = [parameters]
        # implemented = {'t_0', 't_E', 'u_0', 't_eff', 'pi_E_N', 'pi_E_E'}
        # if len(set(parameters) - implemented) > 0:
        #     raise NotImplementedError((
        #         "chi^2 gradient is implemented only for {:}\nCannot work " +
        #         "with {:}").format(implemented, parameters))
        # gradient = {param: 0 for param in parameters}
        #
        # if self.model.n_sources != 1:
        #     raise NotImplementedError("Sorry, chi2 for binary sources is " +
        #                               "not implemented yet")
        # if self.model.n_lenses != 1:
        #     raise NotImplementedError(
        #         'Event.chi2_gradient() works only ' +
        #         'single lens models currently')
        # as_dict = self.model.parameters.as_dict()
        # if 'rho' in as_dict or 't_star' in as_dict:
        #     raise NotImplementedError(
        #         'Event.chi2_gradient() is not working ' +
        #         'for finite source models yet')
        #
        # # Define a Fit given the model and perform linear fit for fs and fb
        # self._update_data_in_model()
        # self.fit = Fit(
        #     data=self.datasets, magnification=self.model.data_magnification)
        # # For binary source cases, the above line would need to be replaced,
        # # so that it uses self.model.fit.
        # if fit_blending is not None:
        #     self.fit.fit_fluxes(fit_blending=fit_blending)
        # else:
        #     self.fit.fit_fluxes()
        #
        # for (i, dataset) in enumerate(self.datasets):
        #     (data, err_data) = dataset.data_and_err_in_chi2_fmt()
        #     factor = data - self.fit.get_chi2_format(data=dataset)
        #     factor *= -2. / err_data**2
        #     if dataset.chi2_fmt == 'mag':
        #         factor *= -2.5 / (log(10.) * Utils.get_flux_from_mag(data))
        #     factor *= self.fit.flux_of_sources(dataset)[0]
        #
        #     kwargs = {}
        #     if dataset.ephemerides_file is not None:
        #         kwargs['satellite_skycoord'] = dataset.satellite_skycoord
        #     trajectory = Trajectory(
        #             dataset.time, self.model.parameters,
        #             self.model.get_parallax(), self.coords, **kwargs)
        #     u_2 = trajectory.x**2 + trajectory.y**2
        #     u_ = np.sqrt(u_2)
        #     d_A_d_u = -8. / (u_2 * (u_2 + 4) * np.sqrt(u_2 + 4))
        #     factor *= d_A_d_u
        #
        #     factor_d_x_d_u = (factor * trajectory.x / u_)[dataset.good]
        #     sum_d_x_d_u = np.sum(factor_d_x_d_u)
        #     factor_d_y_d_u = (factor * trajectory.y / u_)[dataset.good]
        #     sum_d_y_d_u = np.sum(factor_d_y_d_u)
        #     dt = dataset.time[dataset.good] - as_dict['t_0']
        #
        #     # Exactly 2 out of (u_0, t_E, t_eff) must be defined and
        #     # gradient depends on which ones are defined.
        #     if 't_eff' not in as_dict:
        #         t_E = as_dict['t_E'].to(u.day).value
        #         if 't_0' in parameters:
        #             gradient['t_0'] += -sum_d_x_d_u / t_E
        #         if 'u_0' in parameters:
        #             gradient['u_0'] += sum_d_y_d_u
        #         if 't_E' in parameters:
        #             gradient['t_E'] += np.sum(factor_d_x_d_u * -dt / t_E**2)
        #     elif 't_E' not in as_dict:
        #         t_eff = as_dict['t_eff'].to(u.day).value
        #         if 't_0' in parameters:
        #             gradient['t_0'] += -sum_d_x_d_u * as_dict['u_0'] / t_eff
        #         if 'u_0' in parameters:
        #             gradient['u_0'] += sum_d_y_d_u + np.sum(
        #                     factor_d_x_d_u * dt / t_eff)
        #         if 't_eff' in parameters:
        #             gradient['t_eff'] += np.sum(
        #                     factor_d_x_d_u * -dt *
        #                     as_dict['u_0'] / t_eff**2)
        #     elif 'u_0' not in as_dict:
        #         t_E = as_dict['t_E'].to(u.day).value
        #         t_eff = as_dict['t_eff'].to(u.day).value
        #         if 't_0' in parameters:
        #             gradient['t_0'] += -sum_d_x_d_u / t_E
        #         if 't_E' in parameters:
        #             gradient['t_E'] += (
        #                     np.sum(factor_d_x_d_u * dt) -
        #                     sum_d_y_d_u * t_eff) / t_E**2
        #         if 't_eff' in parameters:
        #             gradient['t_eff'] += sum_d_y_d_u / t_E
        #     else:
        #         raise KeyError(
        #             'Something is wrong with ModelParameters in ' +
        #             'Event.chi2_gradient():\n', as_dict)
        #
        #     # Below we deal with parallax only.
        #     if 'pi_E_N' in parameters or 'pi_E_E' in parameters:
        #         parallax = {
        #             'earth_orbital': False,
        #             'satellite': False,
        #             'topocentric': False}
        #         trajectory_no_piE = Trajectory(
        #             dataset.time, self.model.parameters, parallax, self.coords,
        #             **kwargs)
        #         dx = (trajectory.x - trajectory_no_piE.x)[dataset.good]
        #         dy = (trajectory.y - trajectory_no_piE.y)[dataset.good]
        #         delta_E = dx * as_dict['pi_E_E'] + dy * as_dict['pi_E_N']
        #         delta_N = dx * as_dict['pi_E_N'] - dy * as_dict['pi_E_E']
        #         det = as_dict['pi_E_N']**2 + as_dict['pi_E_E']**2
        #
        #         if 'pi_E_N' in parameters:
        #             gradient['pi_E_N'] += np.sum(
        #                 factor_d_x_d_u * delta_N + factor_d_y_d_u * delta_E)
        #             gradient['pi_E_N'] /= det
        #         if 'pi_E_E' in parameters:
        #             gradient['pi_E_E'] += np.sum(
        #                 factor_d_x_d_u * delta_E - factor_d_y_d_u * delta_N)
        #             gradient['pi_E_E'] /= det
        #
        if len(parameters) == 1:
            out = gradient[parameters[0]]
        else:
            out = np.array([gradient[p] for p in parameters])
        return out

    def fit_fluxes(self):
        """
        Fit for the optimal fluxes for each dataset (and its chi2)
        """
        # JCY - I tried, but I could not think of an instance in which
        # it was simpler not to redefine fits every time.
        # Actually, I also could not think of an instance in which you
        # would want to rerun the fits if nothing changes.
        self.fits = []
        for dataset in self.datasets:
            if dataset in self.fix_blend_flux.keys():
                fix_blend_flux = self.fix_blend_flux[dataset]
            else:
                fix_blend_flux = False

            if dataset in self.fix_source_flux.keys():
                fix_source_flux = self.fix_source_flux[dataset]
            else:
                fix_source_flux = False

            # JCY - This needs a unit test.
            if dataset in self.fix_q_flux.keys():
                fix_q_flux = self.fix_q_flux[dataset]
            else:
                if dataset.bandpass in self.fix_q_flux.keys():
                    fix_q_flux = self.fix_q_flux[dataset.bandpass]
                else:
                    fix_q_flux = False

            fit = FitData(
                model=self.model, dataset=dataset,
                fix_blend_flux=fix_blend_flux, fix_source_flux=fix_source_flux,
                fix_q_flux=fix_q_flux)
            fit.update()  # Fit the fluxes and calculate chi2.
            self.fits.append(fit)

    def reset_best_chi2(self):
        """
        Reset :py:attr:`~best_chi2` attribute and its parameters
        (:py:attr:`~best_chi2_parameters`).
        """
        # To be deprecated
        self._best_chi2 = None
        self._best_chi2_parameters = {}

    def _sum(self, data):
        """calculate sum of the data"""
        if self.sum_function == 'numpy.sum':
            return np.sum(data)
        elif self.sum_function == 'math.fsum':
            return fsum(data)
        else:
            raise ValueError(
                'Event.sum_function unrecognized: ' + self.sum_function)

    def _update_data_in_model(self):
        """
        Make sure data here and in self.model are the same. If not, then update
        the ones in self.model. This happens only when the same Model instance
        is used by different instances of Event.
        """
        pass
        # if self.model.datasets != self.datasets:
        #     self.model.set_datasets(self.datasets)

    @property
    def coords(self):
        """
        see :py:class:`~MulensModel.coordinates.Coordinates`
        """
        return self._coords

    @coords.setter
    def coords(self, new_value):
        self._update_coords(coords=new_value)

    def _update_coords(self, coords=None):
        """Set the coordinates as a SkyCoord object"""
        self._coords = Coordinates(coords)

        if self._model is not None:
            self._model.coords = self._coords

        # We run the command below with try, because _update_coords() is called
        # by _set_datasets before self._datasets is set.
        try:
            for dataset in self._datasets:
                dataset.coords = self._coords
        except Exception:
            pass

    @property
    def model(self):
        """an instance of :py:class:`~MulensModel.model.Model`"""
        return self._model

    @model.setter
    def model(self, new_value):
        if not isinstance(new_value, Model):
            raise TypeError((
                    'wrong type of Event.model: {:} instead of ' +
                    'MulensModel').format(type(new_value)))
        self._model = new_value
        # if self._datasets is not None:
        #     self._model.set_datasets(self._datasets)

        if new_value.coords is not None:
            self._update_coords(coords=new_value.coords)

        self.fits = None  # reset the fits if the model changed.

    @property
    def datasets(self):
        """
        a *list* of :py:class:`~MulensModel.mulensdata.MulensData`
        instances.
        """
        return self._datasets

    @datasets.setter
    def datasets(self, new_value):
        self._set_datasets(new_value)

    def _set_datasets(self, new_value):
        """
        sets the value of self._datasets
        can be called by __init__ or @datasets.setter
        passes datasets to property self._model
        """
        if isinstance(new_value, list):
            for dataset in new_value:
                if dataset.coords is not None:
                    self._update_coords(coords=dataset.coords)
        if isinstance(new_value, MulensData):
            if new_value.coords is not None:
                self._update_coords(coords=new_value.coords)
            new_value = [new_value]
        if new_value is None:
            self._datasets = None
            return
        self._datasets = new_value
        # if isinstance(self._model, Model):
        #     self._model.set_datasets(self._datasets)

        self.fits = None  # reset the fits if the data changed

    @property
    def data_ref(self):
        """
        Reference data set for scaling the model fluxes to (for
        plotting). May be set as a
        :py:class:`~MulensModel.mulensdata.MulensData` object or an
        index (*int*). Default is the first data set.

        Returns :
            index (*int*) of the relevant dataset.
        """
        if self._data_ref is None:
            return 0
        else:
            return self._data_ref

    @data_ref.setter
    def data_ref(self, new_value):
        self._data_ref = self._set_data_ref(new_value)

    def _set_data_ref(self, new_value):
        """
        Set reference dataset. Not covered by unit tests.
        """
        if isinstance(new_value, MulensData):
            index = np.where(self.datasets == new_value)
            if len(index[0]) > 1:
                raise ValueError(
                    'Dataset is included in Event.datasets more than once.')

            self._data_ref = index[0]
        elif isinstance(new_value, (int, np.int)):
            self._data_ref = new_value
        else:
            raise TypeError(
                'data_ref must be set using either *int* or *MulensData*: ' +
                '{0}'.format(type(new_value)))

    @property
    def chi2(self):
        """
        *float*

        Chi^2 value. Note this is a static property. It is only updated when
        :py:func:`~fit_fluxes()` or :py:func:`~get_chi2()` is run. So, if you
        change one of the settings be sure to run one of those functions to
        update the chi2.
        """
        return self._chi2

    @chi2.setter
    def chi2(self, new_value):
        self._chi2 = new_value

    @property
    def best_chi2(self):
        """
        *float*

        The smallest value returned by :py:func:`get_chi2()`.
        """
        warnings.warn('best_chi2 will be deprecated in future.', FutureWarning)
        return self._best_chi2

    @property
    def best_chi2_parameters(self):
        """
        *dict*

        Parameters that gave the smallest chi2.
        """
        warnings.warn('best_chi2_parameters will be deprecated in future.',
                      FutureWarning)
        return self._best_chi2_parameters

    @property
    def sum_function(self):
        """
        *str*

        Function used for adding chi^2 contributions. Can be either
        'math.fsum' (default value) or 'numpy.sum'.
        The former is slightly slower and more accurate,
        which may be important for large datasets.
        """
        return self._sum_function

    @sum_function.setter
    def sum_function(self, new_value):
        self._sum_function = new_value

    def clean_data(self):
        """masks outlying datapoints. **Not Implemented.**"""
        raise NotImplementedError("This feature has not been implemented yet")

    def estimate_model_params(self):
        """
        estimates model parameters without fitting them.
        **Not Implemented.**
        """
        raise NotImplementedError("This feature has not been implemented yet")

    def _apply_fit_blending(self, fit_blending):
        warnings.warn(
            'fit_blending option will be deprecated in future.' +
            'To fix the blending, set Event.fix_blend_flux instead.',
            FutureWarning)
        self.fits = None
        if fit_blending is True:
            self.fix_blend_flux = {}
        else:
            for dataset in self.datasets:
                self.fix_blend_flux[dataset] = 0.
