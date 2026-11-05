const StudyTranslations = {
  toggle: '<label class="translation-toggle"><input type="checkbox"> 显示中文</label>',
  phrase(text, escape) {
    const translationStart = text.search(/[（(][^（）()]*\p{Script=Han}/u);
    if (translationStart >= 0) {
      return escape(text.slice(0, translationStart)) +
        '<span class="translation-text">' + escape(text.slice(translationStart)) + '</span>';
    }
    return /\p{Script=Han}/u.test(text)
      ? '<span class="translation-text">' + escape(text) + '</span>'
      : escape(text);
  }
};
