import numpy as np
import math
import matplotlib.pyplot as plt  # XXX probably remove that


class UniformCausticSampling(object):
    def __init__(self, s, q, n_points=1000):
        """
        XXX

        calculations take some time
        https://ui.adsabs.harvard.edu/abs/2008A%26A...491..587C/abstract
        https://ui.adsabs.harvard.edu/abs/2010A%26A...515A..52C/abstract
        """
        self._s = s
        self._q = q
        self._n_points = n_points

        self._get_n_caustics()
        self._get_phi()
        self._integrate()
        self._find_inflections_and_correct()
        self._add_third_caustic()
        self._combine_parameterizations()

    def _combine_parameterizations(self):
        """
        XXX
        """
        pass  # XXX

    def _add_third_caustic(self):
        """
        XXX
        """
        # Previously we had:
        #    caustic_zeta_sum3 = [
        #        caustic_zeta_sum2[i].conjugate() for i in [0, 2, 1]]
        pass  # XXX

    def _get_indexes_of_inflection_points(self, values):
        """
        Find inflection points in give tabulated function.
        """
        diff_ = values[1:] - values[:-1]
        diff = np.concatenate( ([diff_[-2], diff_[-1]], diff_) )
        # diff = np.concatenate( (diff_, [diff_[0], diff_[1]]) )
        out = []
        for i in range(1, len(diff)-1):
            if diff[i-1] > diff[i] and diff[i+1] > diff[i]:
                # out.append(i-1) # XXX
                out.append(i)
        # print("INFLECTIONS:", out)
        return out

    def _zeta(self, z):
        """
        Apply lens equation in complex coordinates and
        shift to center of mass coordinates.
        """
        z_bar = np.conjugate(z)
        zeta = -z + (1./z_bar + self.q/(z_bar+self.s)) / (1. + self.q)
        zeta -= self.s * self.q / (1. + self.q)
        return zeta

    def _find_inflections_and_correct(self):
        """
        Find inflection points of s(phi). In the case of close configuration
        also correct the phase of planetary caustic.
        """
        indexes = self._get_indexes_of_inflection_points(self._sum_1)
        value_1 = [float(i)/self._n_points for i in indexes]
        self._inflections_fractions = {1: value_1}
        cusps_z_1 = [self._z_sum_1[i] for i in indexes]
        if self._n_caustics == 1:
            cusps_z_1 = [self._z_all[indexes[2], 0]] + cusps_z_1
            cusps_z_1 += [c.conjugate() for c in cusps_z_1[1::-1]]
        else:
            if self._n_caustics == 2:
                add = self._z_all[indexes[1], 2]
            else:
                add = self._z_all[indexes[1], 3]
            cusps_z_1 = [add] + cusps_z_1
            cusps_z_1 += [cusps_z_1[0].conjugate()]

        cusps_zeta_1 = [self._zeta(z) for z in cusps_z_1]

        if self._n_caustics == 1:
            self._which_caustic = np.array([0., 1.])
            return

        indexes = self._get_indexes_of_inflection_points(self._sum_2)
        value_2 = [float(i)/self._n_points for i in indexes]
        self._inflections_fractions[2] = value_2
        cusps_z_2 = [self._z_sum_2[i] for i in indexes]
        if self._n_caustics == 2:
            cusps_z_2 = [self._z_all[indexes[1], 0]] + cusps_z_2
            cusps_z_2 += [cusps_z_2[0].conjugate()]

        cusps_zeta_2 = [self._zeta(z) for z in cusps_z_2]

        #if self._n_caustics == 3:
            #arg = np.argmin([np.abs(z) for z in cusps_zeta_2])
            #self._shift = self._sum_2[indexes[arg] - 1]
# HERE
# XXX - currently we skip this part because it produces an artifact
# in self.plot_caustic()
        if False:
        # Only for close configuration there is a need to modify self._sum_2
        # in order to make inflection point closer to 0.
        #  if self._n_caustics == 3:
            arg = np.argmin([np.abs(z) for z in cusps_zeta_2])
            shift = indexes[arg] - 1
            # shift = 0
            # shift = indexes[arg]
            # print("SHIFT", shift)
            d_1 = self._sum_2[-1] - self._sum_2[-2]
            d_2 = self._sum_2[1] - self._sum_2[0]
            value_shift = self._sum_2[-1] + (d_1 + d_2) / 2.
            self._sum_2 = np.roll(self._sum_2, -shift)
            self._z_all_2 = np.roll(self._z_all, -shift, axis=0)
            # XXX self._z_sum_2
            self._z_index_sum_2 = np.roll(self._z_index_sum_2, shift)
            self._sum_2[:-shift] -= value_shift
            self._sum_2 -= self._sum_2[0]

            indexes = self._get_indexes_of_inflection_points(self._sum_2)
            value_2 = [float(i)/self._n_points for i in indexes]
            self._inflections_fractions[2] = value_2
            value_3 = [self._inflections_fractions[2][i] for i in [0, 2, 1]]
            self._inflections_fractions[3] = value_3
            cusps_z_2 = [self._z_sum_2[i] for i in indexes]
            cusps_zeta_2 = [self._zeta(z) for z in cusps_z_2]

        # XXX This seems unused
        if self._n_caustics == 3:
            indexes = [indexes[i] for i in [0, 2, 1]]
            cusps_z_3 = [self._z_sum_2[i].conjugate() for i in indexes]
            cusps_zeta_3 = [self._zeta(z) for z in cusps_z_3]

        length_1 = 2. * self._sum_1[-1]
        lengths_sum = length_1
        lengths = [length_1]
        if self._n_caustics > 1:
            length_2 = self._sum_2[-1]
            if self._n_caustics == 2:
                length_2 *= 2.
            lengths_sum += length_2
            lengths += [length_1 + length_2]
            if self._n_caustics == 3:
                length_3 = length_2
                lengths_sum += length_2
                lengths += [lengths[-1] + length_3]
        self._which_caustic = np.array([0.] + lengths) / lengths_sum
# XXX  what we want to remember from above:
# - length_
# - indexes
# - cusps_z_
# - cusps_zeta_

    def _find_nearest_index(self, array, value):
        """
        returns element of array that is closest to value
        """
        idx = (np.abs(array - value)).argmin()
        return array[idx]

    def _critical_curve(self, phi):
        """
        Calculate a point on critical curve - see eq. 6 in Cassan 2008.
        """
        coeffs = [0., 0., 0., 2.*self.s, 1.]
        exp_i_phi = np.exp(1j * phi)
        coeffs[0] = -self.s * self.s * exp_i_phi / (1. + self.q)
        coeffs[1] = -2. * self.s * exp_i_phi / (1. + self.q)
        coeffs[2] = self.s * self.s - exp_i_phi

        roots = np.polynomial.polynomial.polyroots(np.array(coeffs))

        if self._n_caustics == 3:
            if self._critical_curve_previous is not None:
                # This makes sure we're following right branch.
                new_roots = np.array([0.+0.j, 0.+0.j, 0.+0.j, 0.+0.j])
                for (i, v) in enumerate(self._critical_curve_previous):
                    new_roots[i] = self._find_nearest_index(roots, v)
                roots = new_roots
            self._critical_curve_previous = roots

        return roots

    def _dz_dphi(self, z):
        """
        Eq. 11 from Cassan (2008)
        """
        z_plus_d = z + self.s
        z_plus_d_2 = z_plus_d**2
        z_plus_d_3 = z_plus_d_2 * z_plus_d
        q_z_2 = self.q * z * z
        value = (z_plus_d_2 + q_z_2) * z_plus_d * z / (z_plus_d_3 + z * q_z_2)
        return 0.5j * value

    def _dz_bar_dphi(self, z_bar):
        """
        almost the same as eq. 11 from Cassan (2008)
        """
        return -self._dz_dphi(z_bar)

    def _dzeta_dphi(self, z, phi):
        """
        Eq. (9) and (11) from Cassan (2008)
        """
        dz_dphi_ = self._dz_dphi(z)
        dz_bar_dphi_ = self._dz_bar_dphi(np.conjugate(z))
        return dz_dphi_ + np.exp(1j * phi) * dz_bar_dphi_

    def _integrate(self):
        """
        Main integration for Cassan (2008) parameterization.
        It sets internal variables:
        - self._z_all
        - self._sum_1
        - self._sum_2
        - self._z_sum_1
        - self._z_sum_2
        - self._z_index_sum_1
        - self._z_index_sum_2
        """
        size = (self._n_points, 4)
        self._z_all = np.zeros(size, dtype=np.complex128)
        self._sum_1 = np.zeros(self._n_points)
        self._z_sum_1 = np.zeros(self._n_points, dtype=np.complex128)
        self._z_index_sum_1 = np.zeros(self._n_points, dtype=int)
        if self._n_caustics > 1:
            self._sum_2 = np.zeros(self._n_points)
            self._z_sum_2 = np.zeros(self._n_points, dtype=np.complex128)
            self._z_index_sum_2 = np.zeros(self._n_points, dtype=int)
            # XXX removed not unused code
            #if self._n_caustics == 3:
                #self._z_index_sum_1 += 0
                #self._z_index_sum_2 += 2
        self._critical_curve_previous = None

        for (i, phi) in enumerate(self._phi):
            self._z_all[i] = self._critical_curve(phi)
            if i == 0:
                continue

            if self._n_caustics == 1:
                self._z_index_sum_1[i] = int(phi / np.pi)
                self._z_sum_1[i] = self._z_all[i, self._z_index_sum_1[i]]
                abs_1 = abs(self._dzeta_dphi(self._z_sum_1[i], phi))
                self._sum_1[i] = self._sum_1[i-1] + abs_1 * self._d_phi
            if self._n_caustics > 1:
                if self._n_caustics == 2:
                    self._z_index_sum_2[i] = int(phi / np.pi)
                    self._z_index_sum_1[i] = self._z_index_sum_2[i] + 2
                if self._n_caustics == 3:
                    signs = 1. / np.conjugate(self._z_all[i])
                    signs = (signs - self._z_all[i]).imag
                    if signs[1] * signs[2] >= 0.:
                        args = [
                            self.s, self.q, self._n_points, i, self._z_all[i]]
                        raise ValueError("Critical error: {:}".format(args))
                    if signs[1] < 0.:
                        self._z_index_sum_2[i] = 2
                    else:
                        self._z_index_sum_2[i] = 1
                self._z_sum_1[i] = self._z_all[i, self._z_index_sum_1[i]]
                self._z_sum_2[i] = self._z_all[i, self._z_index_sum_2[i]]
                abs_1 = abs(self._dzeta_dphi(self._z_sum_1[i], phi))
                abs_2 = abs(self._dzeta_dphi(self._z_sum_2[i], phi))
                self._sum_1[i] = self._sum_1[i-1] + abs_1 * self._d_phi
                self._sum_2[i] = self._sum_2[i-1] + abs_2 * self._d_phi

    def _get_phi(self):
        """
        Prepare internal variables:
            self._phi - gives all phi values used for integration
            self._d_phi - step between adjacent phi values
        """
        phi_begin = 0.
        phi_end = 2. * np.pi - 1e-14
        if self._n_caustics == 1:
            phi_end = 4. * np.pi - 1e-14
        self._d_phi = (phi_end - phi_begin) / self._n_points
        self._phi = np.linspace(phi_begin, phi_end, self._n_points)

    def _get_n_caustics(self):
        """
        Get number of caustics: 1, 2, or 3.
        """
        limit = (1. + self.q) / (1. + self.q**(1./3.))**3
        if self.s > 1. / math.sqrt(limit):
            self._n_caustics = 2
        elif self.s < math.pow(limit, 0.25):
            self._n_caustics = 3
        else:
            self._n_caustics = 1

    def get_standard_parameters(self, x_caustic_in, x_caustic_out,
                                t_caustic_in, t_caustic_out):
        """
        Get standard binary lens parameters (i.e., t_0, u_0, t_E, alpha)
        based on provided parameters.

        Note that this function quite frequently raises ValueError exception.
        That is because not all (s, q, x_caustic_in and x_caustic_out)
        correspond to real trajectories.

        Keywords :
            x_caustic_in: *float*
                Curvelinear coordinate of caustic entrance.
                Must be in (0, 1) range.

            x_caustic_out: *float*
                Curvelinear coordinate of caustic exit.
                Must be in (0, 1) range.

            t_caustic_in: *float*
                Epoch of caustic entrance.

            t_caustic_out: *float*
                Epoch of caustic exit.

        Returns :
            parameters: *dict*
                Dictionary with standard binary parameters, i.e, keys are
                ``t_0``, ``u_0``, ``t_E``, and ``alpha``.
        """
        # XXX do we need t_caustic_in < t_caustic_out check here?
        caustic_in = self.which_caustic(x_caustic_in)
        caustic_out = self.which_caustic(x_caustic_out)
        if caustic_in != caustic_out:
            message = (
                "Function get_standard_parameters() got curvelinear caustic " +
                "coordinates on different caustics.\n" +
                "x_caustic_in = {:} is on caustic ".format(x_caustic_in) +
                "{:} and\n".format(caustic_in) +
                "x_caustic_out = {:} is on caustic ".format(x_caustic_out) +
                "{:}".format(caustic_out))
            raise ValueError(message)

        zeta_in = self.caustic_point(x_caustic_in)
        zeta_out = self.caustic_point(x_caustic_out)

        u_0 = zeta_out.real*zeta_in.imag - zeta_out.imag*zeta_in.real
        u_0 /= abs(zeta_out - zeta_in)
        if zeta_out.real == zeta_in.real:
            alpha = 0.5 * np.pi * np.sign(zeta_out.imag - zeta_in.imag)
        else:
            diff = zeta_out.imag - zeta_in.imag
            alpha = np.arctan(diff / (zeta_out.real - zeta_in.real))
            alpha += np.pi * np.heaviside(zeta_in.real-zeta_out.real, .5)
        alpha *= 180. / np.pi
        if alpha < 0.:
            alpha += 360.
        t_E = (t_caustic_out - t_caustic_in) / abs(zeta_out - zeta_in)
        t_0 = ((zeta_out + zeta_in) / (zeta_out - zeta_in)).real
        t_0 *= 0.5 * (t_caustic_in - t_caustic_out)
        t_0 += 0.5 * (t_caustic_out + t_caustic_in)
        return {'t_0': t_0, 'u_0': u_0, 't_E': t_E, 'alpha': alpha}

    def allowed_ranges(self, x_caustic):
        """
        For given value of x_caustic_in or _out get 1 or 2 ranges in
        which the other parameter has to be (required condition, but not
        necessarily enough).

        XXX
        """
        caustic = self.which_caustic(x_caustic)
        print(self._inflections_fractions)
        print(self._which_caustic)
        pass  # XXX

    def _mirror_normalize_to_0_1(self, x, x_min=0., x_max=1.):
        """
        Normalizes input to 0-1 range but in special way,
        which considers the middle point.
        """
        if x < x_min or x > x_max:
            msg = "problem in _mirror_normalize: {:} {:} {:}"
            raise ValueError(msg.format(x, x_min, x_max))
        middle = (x_min + x_max) / 2.
        if x < middle:
            xx = (x - x_min) / (middle - x_min)
            return (xx, False)
        else:
            xx = (x_max - x) / (x_max - middle)
            return (xx, True)

    def caustic_point(self, x_caustic):
        """
        Calculate caustic position corresponding to given x_caustic.

        Keywords :
            x_caustic: *float*
                Curvelinear coordinate of the point considered.
                Has to be in 0-1 range.

        Returns :
            point: *numpy.complex128*
                Caustic point in complex coordinates.
        """
        caustic = self.which_caustic(x_caustic)

        if self._n_caustics < 3 or caustic == 1:
            (fraction_in_caustic, flip) = self._mirror_normalize_to_0_1(
                x_caustic, self._which_caustic[caustic-1],
                self._which_caustic[caustic])
        else:
            in_caustic = x_caustic - self._which_caustic[caustic-1]
            diff = (
                self._which_caustic[caustic] - self._which_caustic[caustic-1])
            fraction_in_caustic = in_caustic / diff
            flip = False

        if caustic == 1:
            sum_use = self._sum_1
            z_use = self._z_sum_1
        else:
            sum_use = self._sum_2
            z_use = self._z_sum_2
        sum_ = fraction_in_caustic * sum_use[-1]
        phi_interp = np.interp([sum_], sum_use, self._phi)[0]
        z_interp = np.interp([phi_interp], self._phi, z_use)[0]
        # z_interp = np.interp([sum_], sum_use, z_use)[0] # XXX
        zeta = self._zeta(z_interp)
        if flip or caustic == 3:
            zeta = zeta.conjugate()
        return zeta

    def which_caustic(self, x_caustic):
        """
        Indicates on which caustic given point is.

        Keywords :
            x_caustic: *float*
                Curvelinear coordinate to be checked

        Returns :
            i_caustic: *int*
                Number indicating the caustic:

                ``1`` - central caustic,

                ``2`` - planetary caustic; for close configuration it is
                the upper of the two planetary caustics,

                ``3`` - lower planetary caustic.
        """
        if x_caustic > 1.:
            raise ValueError('Got x_caustic > 1 : {:}'.format(x_caustic))
        if x_caustic < 0.:
            raise ValueError('Got x_caustic < 0 : {:}'.format(x_caustic))
        if self._n_caustics == 1:
            return 1
        return np.searchsorted(self._which_caustic, x_caustic)

    @property
    def s(self):
        """
        *float*

        separation of the two lens components relative to Einstein ring size
        """
        return self._s

    @property
    def q(self):
        """
        *float*

        Mass ratio.
        """
        return self._q

    def _plot_caustic(self, n_points=200):
        """
        Plot caustic using uniform sampling and color scale
        """
        x = np.zeros(n_points)
        y = np.zeros(n_points)
        color = np.linspace(0, 1, n_points+2)[1:-1]
        for (i, value) in enumerate(color):
            c = self.caustic_point(value)
            x[i] = c.real
            y[i] = c.imag
        plt.scatter(x, y, c=color)
        plt.axis('equal')
        plt.colorbar()

    def _plot_full(self, x_caustic_in, x_caustic_out, t_caustic_in,
                   t_caustic_out, n_points=200):
        """
        Plot caustic and trajectory - useful for checks of model parameter
        calculations.
        """
        self._plot_caustic(n_points=n_points)
        params = self.get_standard_parameters(x_caustic_in, x_caustic_out,
                                              t_caustic_in, t_caustic_out)
        params['s'] = self.s
        params['q'] = self.q
        model = MM.Model(params)
        model.plot_trajectory(t_start=t_caustic_in, t_stop=t_caustic_out)
        model.plot_trajectory([params['t_0']], marker='X', arrow=False)

        c_in = self.caustic_point(x_caustic_in)
        c_out = self.caustic_point(x_caustic_out)
        plt.scatter(c_in.real, c_in.imag, marker='X', c='pink')
        plt.scatter(c_out.real, c_out.imag, marker='X', c='red')

        txt = "s = {:} q = {:} x_caustic_in = {:} x_caustic_out = {:}"
        plt.title(txt.format(self.s, self.q, x_caustic_in, x_caustic_out))
        plt.tight_layout()
