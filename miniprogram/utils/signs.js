const signs = [
  { key: "aries", cn: "白羊座", en: "Aries", range: "3.21 - 4.19", element: "火象", elementKey: "fire", icon: "♈︎" },
  { key: "taurus", cn: "金牛座", en: "Taurus", range: "4.20 - 5.20", element: "土象", elementKey: "earth", icon: "♉︎" },
  { key: "gemini", cn: "双子座", en: "Gemini", range: "5.21 - 6.21", element: "风象", elementKey: "air", icon: "♊︎" },
  { key: "cancer", cn: "巨蟹座", en: "Cancer", range: "6.22 - 7.22", element: "水象", elementKey: "water", icon: "♋︎" },
  { key: "leo", cn: "狮子座", en: "Leo", range: "7.23 - 8.22", element: "火象", elementKey: "fire", icon: "♌︎" },
  { key: "virgo", cn: "处女座", en: "Virgo", range: "8.23 - 9.22", element: "土象", elementKey: "earth", icon: "♍︎" },
  { key: "libra", cn: "天秤座", en: "Libra", range: "9.23 - 10.23", element: "风象", elementKey: "air", icon: "♎︎" },
  { key: "scorpio", cn: "天蝎座", en: "Scorpio", range: "10.24 - 11.21", element: "水象", elementKey: "water", icon: "♏︎" },
  { key: "sagittarius", cn: "射手座", en: "Sagittarius", range: "11.22 - 12.21", element: "火象", elementKey: "fire", icon: "♐︎" },
  { key: "capricorn", cn: "摩羯座", en: "Capricorn", range: "12.22 - 1.19", element: "土象", elementKey: "earth", icon: "♑︎" },
  { key: "aquarius", cn: "水瓶座", en: "Aquarius", range: "1.20 - 2.18", element: "风象", elementKey: "air", icon: "♒︎" },
  { key: "pisces", cn: "双鱼座", en: "Pisces", range: "2.19 - 3.20", element: "水象", elementKey: "water", icon: "♓︎" }
];

function findSign(key) {
  return signs.find((sign) => sign.key === key) || signs[0];
}

module.exports = {
  findSign,
  signs
};
