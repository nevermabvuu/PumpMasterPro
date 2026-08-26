const CURVE_CONVERSIONS = {
    q: {'m3h': 1.0, 'ls': 0.277778, 'usgpm': 4.40287, 'impgpm': 3.66621}
};
const units = {q: 'ls'};
const baseQ = 'ls'; // because pump.unit_q is 'ls'
let fX = (CURVE_CONVERSIONS.q[units.q] || 1.0) / (CURVE_CONVERSIONS.q[baseQ] || 1.0);
console.log('fX:', fX);