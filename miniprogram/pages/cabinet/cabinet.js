const dataset = require('../../data/dataset.js');

Page({
  data: {
    dataVersion: dataset.dataVersion,
    cabinetCount: dataset.cabinets.length,
    hasCabinets: dataset.cabinets.length > 0
  }
});
