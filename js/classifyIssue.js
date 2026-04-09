(function () {
  function classifyIssue(noteText) {
    const source = String(noteText || "");
    const categories = (window.APP_CONFIG && window.APP_CONFIG.ISSUE_CATEGORIES) || {};
    const matched = [];

    Object.keys(categories).forEach((categoryName) => {
      const keywords = Array.isArray(categories[categoryName].keywords)
        ? categories[categoryName].keywords
        : [];
      const isMatched = keywords.some((kw) => kw && source.includes(kw));
      if (isMatched) matched.push(categoryName);
    });

    return matched.length > 0 ? matched : ["기타"];
  }

  window.classifyIssue = classifyIssue;
})();
