unify_symbols = """
function toHalfWidth(strVal){
  var halfVal = strVal.replace(/[！-～]/g,
    function( tmpStr ) {
      if (tmpStr.charCodeAt(0) >= "０".charCodeAt(0) && tmpStr.charCodeAt(0) <= "９".charCodeAt(0)) {
          return tmpStr;
      }
      if (tmpStr.charCodeAt(0) >= "Ａ".charCodeAt(0) && tmpStr.charCodeAt(0) <= "Ｚ".charCodeAt(0)) {
          return tmpStr;
      }
      if (tmpStr.charCodeAt(0) >= "ａ".charCodeAt(0) && tmpStr.charCodeAt(0) <= "ｚ".charCodeAt(0)) {
          return tmpStr;
      }
      return String.fromCharCode( tmpStr.charCodeAt(0) - 0xFEE0 );
    }
  );
 
  return halfVal.replace(/”/g, "\\"")
    .replace(/’/g, "'")
    .replace(/、/g, ",")
    .replace(/‘/g, "`")
    .replace(/￥/g, "\\\\")
    .replace(/　/g, " ")
    .replace(/〜/g, "~");
}
text = toHalfWidth(text)
"""

unify_numbers = """
text = text.replace(/[０-９]/g, function(s) {
    return String.fromCharCode(s.charCodeAt(0) - 0xFEE0);
});
"""

unify_alphas = """
text = text.replace(/[Ａ-Ｚａ-ｚ]/g, function(s) {
    return String.fromCharCode(s.charCodeAt(0) - 0xFEE0);
});
"""

davinci_003_base_prompt = """私は、javascriptでコードを書きます。変数 text に対し、指示を適用して output を定義します。

指示:
<INPUT>

コード:
let text = "<INPUT_DATA>";"""

gpt_chat_base_prompt = """指示:
<INPUT>

コード:
let text = "<INPUT_DATA>";"""

gpt_system_chat_base_prompt = """JavaScriptコードを作成するAIです。会話はできません。コードブロックのみを作成します。
変数 text に対し、指示を適用して結果を `output` という変数に定義するコードを書きます。(変数名は `output` でなければなりません. また、文字列としてセットする必要があります。)
ユーザーからの入力に登場する `<INPUT_DATA>` はプレースホルダーであり、`text` が変数として定義されていることを前提に続きのコードを書きます。
要件に基づいたコードを提供し、完成したコード以外を結果に含みません。
余計なメッセージはありませんので、コードの内容にだけ焦点を当てて注力します。
了解しましたという言葉等、コードの実行に妨げとなる文言などは一切出力しません。
`以下のJavaScriptコードは、指定された要件を満たします。` などという説明の言葉も一切出力しません。"""