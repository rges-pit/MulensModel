import numpy as np
from math import fsum
from astropy.coordinates import SkyCoord
import astropy.units as u

from MulensModel.utils import Utils
from MulensModel.fit import Fit
from MulensModel.mulensdata import MulensData
from MulensModel.model import Model

            
class Event(object):
    """
    Allows a model to be fit to datasets.

    Arguments :

        :py:obj:`datasets` (required): The data; a
            :py:class:`~MulensModel.mulensdata.MulensData` object or
            list of MulensData objects

        :py:obj:`model` (required): a
            :py:class:`~MulensModel.model.Model` object

        :py:obj:`coords` (optional): the coordinates of the event
            (RA, Dec)

    """
    def __init__(self, datasets=None, model=None, coords=None):
        """
        Create an Event object, which allows a model to be fit to datasets.

        Arguments :
            :py:obj:`datasets` (required): The data; a
                :py:class:`~MulensModel.mulensdata.MulensData` object
                or list of MulensData objects

            :py:obj:`model` (required): a
            :py:class:`~MulensModel.model.Model` object

            :py:obj:`coords` (optional): the coordinates of the event
            (RA, Dec)
        """
        #Initialize self._model (and check that model is defined)
        if isinstance(model, Model):
            self._model = model
        elif model is None:
            self._model = None
        else:
            raise TypeError('incorrect argument model of class Event()')

        #Initialize self._datasets (and check that datasets is defined)
        if isinstance(datasets, (list, tuple, MulensData)) or datasets is None:
            self._set_datasets(datasets)
        else:
            raise TypeError('incorrect argument datasets of class Event()')

        #Set event coordinates
        if coords is not None:
            self._update_coords(coords=coords)
        else:
            self._coords = None

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

    @property
    def data_ref(self):
        """
        Reference data set for scaling the model fluxes to (for
        plotting). May be a
        :py:class:`~MulensModel.mulensdata.MulensData` object or an
        index (*int*). Default is the first data set.
        """
        return self.model.data_ref
        
    @data_ref.setter
    def data_ref(self, new_value):
        self.model.data_ref = new_value

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
        if isinstance(self._model, Model):
            self._model.set_datasets(self._datasets)

    @property
    def model(self):
        """an instance of :py:class:`~MulensModel.model.Model`"""
        return self._model

    @model.setter
    def model(self, new_value):
        if not isinstance(new_value, Model):
            raise TypeError(('wrong type of Event.model: {:} instead of ' +
                'MulensModel').format(type(new_value)))
        self._model = new_value
        if self._datasets is not None:
            self._model.set_datasets(self._datasets)

        if new_value.coords is not None:
            self._update_coords(coords=new_value.coords)

    @property
    def coords(self):
        """
        *astropy.coordinates.SkyCoord* object

        The event sky coordinates (RA, Dec). May be set as a *string*
        or *SkyCoord* object, e.g.

        '18:00:00 -30:00:00'

        '18h00m00s -30d00m00s'

        SkyCoord('18:00:00 -30:00:00', unit=(u.hourangle, u.deg))
        
        where u is defined in "import astropy.units as u"
        """
        return self._coords
    
    @coords.setter
    def coords(self, new_value):
        self._update_coords(coords=new_value)

    @property
    def ra(self):
        """
        Right Ascension. May be set as a *string*, e.g. '15:30:00' or
        '15h30m00s'.
        """
        return self._coords.ra

    @ra.setter
    def ra(self, new_value):
        try:
            self._coords.ra = new_value
        except AttributeError:
            if self._coords is None:
                self._coords = SkyCoord(
                    new_value, 0.0, unit=(u.hourangle, u.deg))
            else:
                self._coords = SkyCoord(
                    new_value, self._coords.dec, unit=(u.hourangle, u.deg)) 
        self._update_coords(coords=self._coords)

    @property
    def dec(self):
        """
        Declination. May be set as a *string*, e.g '15:30:00' or '15d30m00s'
        """
        return self._coords.dec

    @dec.setter
    def dec(self, new_value):
        try:
            self._coords.dec = new_value
        except AttributeError:
            if self._coords is None:
                self._coords = SkyCoord(
                    0.0, new_value, unit=(u.hourangle, u.deg))
            else:
                self._coords = SkyCoord(
                    self._coords.ra, new_value, unit=(u.hourangle, u.deg))
        self._update_coords(coords=self._coords)

    def _update_coords(self, coords=None):
        """Set the coordinates as a SkyCoord object"""
        if isinstance(coords, SkyCoord):
            self._coords = coords
        else:
            self._coords = SkyCoord(coords, unit=(u.hourangle, u.deg))

        if self._model is not None:
            self._model.coords = self._coords

        # We run the command below with try, because _update_coords() is called
        # by _set_datasets before self._datasets is set. 
        try:
            for dataset in self._datasets:
                dataset.coords = self._coords
        except Exception:
            pass

    def get_chi2(self, fit_blending=None):
        """
        Calculates chi^2 of current model by fitting for source and 
        blending fluxes.

        Parameters :
            fit_blending : boolean, optional
                If True, then the blend flux is a free parameter. If
                False, the blend flux is fixed at zero.  Default is
                the same as :py:func:`MulensModel.fit.Fit.fit_fluxes()`.

        Returns :
            chi2 : float
                Chi^2 value

        """
        chi2_per_point = self.get_chi2_per_point(
            fit_blending=fit_blending)
        #Calculate chi^2 given the fit
        chi2 = []
        for i, dataset in enumerate(self.datasets):
            #Calculate chi2 for the dataset excluding bad data 
            select = np.logical_not(dataset.bad)
            chi2.append(fsum(chi2_per_point[i][select]))

        self.chi2 = fsum(chi2)
        return self.chi2

    def get_chi2_per_point(self, fit_blending=None):
        """Calculates chi^2 for each data point of the current model by
        fitting for source and blending fluxes.

        Parameters :
            fit_blending : *boolean*, optional
                Are we fitting for blending flux? If not then it is
                fixed to 0.  Default is the same as
                :py:func:`MulensModel.fit.Fit.fit_fluxes()`.

        Returns :
            chi2 : *np.ndarray*  
                Chi^2 contribution from each data point,
                e.g. chi2[obs_num][k] returns the chi2 contribution
                from the *k* th point of observatory *obs_num* .
        """
       #Define a Fit given the model and perform linear fit for fs and fb
        self.fit = Fit(data=self.datasets, 
                       magnification=self.model.data_magnification) 
        if fit_blending is not None:
            self.fit.fit_fluxes(fit_blending=fit_blending)
        else:
            self.fit.fit_fluxes()

        #Calculate chi^2 given the fit
        chi2_per_point = []
        for i, dataset in enumerate(self.datasets):
            diff = dataset._brightness_input \
                 - self.fit.get_input_format(data=dataset)
            chi2_per_point.append(
                (diff / dataset._brightness_input_err)**2)

        chi2_per_point = np.array(chi2_per_point)
        return chi2_per_point


    def get_ref_fluxes(self, data_ref=None):
        """
        see :py:func:`MulensModel.model.Model.get_ref_fluxes()`
        """
        return self.model.get_ref_fluxes(data_ref=data_ref)

    def plot_model(self, **kwargs):
        """
        see :py:func:`MulensModel.model.Model.plot_lc()`
        """
        self.model.plot_lc(**kwargs)

    def plot_data(self, **kwargs):
        """
        see :py:func:`MulensModel.model.Model.plot_data()`
        """
        self.model.plot_data(**kwargs)

    def plot_residuals(self,**kwargs):
        """
        see :py:func:`MulensModel.model.Model.plot_residuals()`
        """
        self.model.plot_residuals(**kwargs)

    def clean_data(self):
        """masks outlying datapoints. Not Implemented."""
        raise NotImplementedError("This feature has not been implemented yet")

    def estimate_model_params(self):
        """estiamtes model parameters without fitting them. Not Implemented"""
        raise NotImplementedError("This feature has not been implemented yet")
