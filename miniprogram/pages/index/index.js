const { signs } = require("../../utils/signs");

Page({
  data: {
    signs,
    period: "daily"
  },

  selectPeriod(event) {
    this.setData({ period: event.currentTarget.dataset.period });
  },

  openDetail(event) {
    const sign = event.currentTarget.dataset.sign;
    wx.navigateTo({
      url: `/pages/detail/detail?sign=${sign}&period=${this.data.period}`
    });
  }
});
