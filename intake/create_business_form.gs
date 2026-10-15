/**
 * create_business_form.gs
 * -----------------------------------------------------------------------------
 * Colorado Farm Trail — "Add my business to the map" intake form.
 *
 * This is a Google Apps Script (JavaScript). It is the version-controlled source
 * of truth for the public submission form. Nothing in this repo runs it — you
 * run it ONCE, by hand, in the Apps Script editor:
 *
 *   1. Go to https://script.google.com  ->  New project
 *   2. Delete the starter code, paste this whole file in
 *   3. Run  ->  createBusinessForm  (authorize the requested scopes when asked)
 *   4. Open View -> Logs (or Executions) and copy the two URLs it prints:
 *        - PUBLISHED URL  -> paste into index.html's "Add my business" button
 *        - EDIT URL       -> paste into docs/BUSINESS_SUBMISSIONS.md for later edits
 *   5. A linked Google Sheet is created automatically to collect responses.
 *
 * Re-running createBusinessForm() creates a BRAND NEW form + sheet each time.
 * Only run it again if you want to start over; otherwise edit the live form
 * via its EDIT URL.
 *
 * The question titles below deliberately mirror the columns in
 * data-compiled/farm_fresh_directory_mymaps.csv so a maintainer can copy a
 * response row almost straight into the CSV. Latitude/Longitude and State are
 * NOT asked of submitters — the maintainer geocodes the address (State is always
 * CO; the Python build script validates Colorado bounds).
 * -----------------------------------------------------------------------------
 */

// Category options — keep in sync with the CATS object in index.html.
// "Other" is intentionally omitted here: it is added as a native free-text
// "Other:" option via .showOtherOption(true) so submitters can describe a
// category we don't list. The maintainer buckets that text into an existing
// CATS category or into the map's "Other" bucket when adding the CSV row.
var CATEGORIES = [
  "Farmers' Market",
  "CSA Farm",
  "On-Farm / Ranch Sales",
  "Roadside Market",
  "U-Pick",
  "Agritourism",
  "Winery",
  "Garden Center / Greenhouse",
  "Restaurant",
  "Wholesale Grower"
];

var MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

// Set true if you want an email sent to the maintainer on every submission.
// Leave false for v1 (form creation only).
var ENABLE_SUBMIT_NOTIFICATIONS = false;
var NOTIFY_EMAIL = ""; // e.g. "coloradofarmtrail@gmail.com" — required if the flag above is true.

/**
 * Main entry point. Run this from the Apps Script editor.
 */
function createBusinessForm() {
  var form = FormApp.create('Add my business to the Colorado Farm Trail')
    .setDescription(
      'Add your Colorado farm, market, CSA, farm stand, U-pick, winery, or ' +
      'agritourism spot to the free Colorado Farm Trail map. It costs nothing. ' +
      'We review every submission before it appears on the map, so please give ' +
      'us accurate details. Fields marked * are required.'
    )
    .setConfirmationMessage(
      'Thanks! We review submissions before adding them to the map, so it may ' +
      'take a little while to appear. — Colorado Farm Trail'
    )
    .setCollectEmail(false)      // avoid forcing a Google sign-in on submitters
    .setAllowResponseEdits(false)
    .setLimitOneResponsePerUser(false);

  // --- Identity ---------------------------------------------------------------
  form.addTextItem()
    .setTitle('Business Name')
    .setHelpText('The name as you want it shown on the map.')
    .setRequired(true);

  // Checkboxes (not single-choice): a producer can belong to several categories
  // — e.g. an On-Farm store that is also a U-Pick and does Agritourism. The
  // maintainer lists them in the CSV with the primary (pin-defining) one first.
  form.addCheckboxItem()
    .setTitle('Category')
    .setHelpText('Check every category that fits your operation — your pin can ' +
      'appear under more than one. If none fit, check "Other" and tell us what you are.')
    .setChoiceValues(CATEGORIES)
    .showOtherOption(true)   // adds a native "Other:" choice with a free-text box
    .setRequired(true);

  // --- Location ---------------------------------------------------------------
  form.addTextItem()
    .setTitle('Address')
    .setHelpText('Street address (or a nearby cross-street / description if there is no street number).')
    .setRequired(true);

  form.addTextItem().setTitle('City');
  form.addTextItem().setTitle('County');
  form.addTextItem()
    .setTitle('Zip')
    .setHelpText('5-digit ZIP code.');

  // Google Forms has no live address autocomplete, so we ask submitters to do
  // the "searching" on Google Maps and paste the resulting link. The maintainer
  // extracts precise Latitude/Longitude from this link when adding the CSV row.
  form.addTextItem()
    .setTitle('Google Maps link')
    .setHelpText(
      'Optional, but the best way to get your pin in exactly the right spot: ' +
      'search your business on Google Maps, tap Share, Copy link, and paste it ' +
      'here (e.g. https://maps.app.goo.gl/...). If you have no Maps listing yet, ' +
      'a dropped-pin link works too — leave blank if you are unsure.'
    );

  // --- Contact ----------------------------------------------------------------
  form.addTextItem().setTitle('Phone');

  form.addMultipleChoiceItem()
    .setTitle('Call first?')
    .setHelpText('Should visitors call ahead before showing up?')
    .setChoiceValues(['No', 'Yes']);

  form.addTextItem()
    .setTitle('Website')
    .setHelpText('Full URL, e.g. https://yourfarm.com');

  form.addTextItem()
    .setTitle('Email')
    .setHelpText('Public contact email (may be shown on the map).');

  form.addTextItem()
    .setTitle('Facebook')
    .setHelpText('Full URL to your Facebook page, if any.');

  form.addTextItem()
    .setTitle('Instagram')
    .setHelpText('Full URL or @handle for Instagram, if any.');

  // --- Details ----------------------------------------------------------------
  form.addParagraphTextItem()
    .setTitle('Hours')
    .setHelpText('When are you open? Free text, e.g. "Sat 8am-1pm; Wed 3-6pm".');

  form.addCheckboxItem()
    .setTitle('Months Open')
    .setHelpText('Check every month you are typically open.')
    .setChoiceValues(MONTHS);

  form.addParagraphTextItem()
    .setTitle('Products')
    .setHelpText('What do you sell? Comma-separated, e.g. "Tomatoes, Peaches, Honey, Eggs".');

  form.addMultipleChoiceItem()
    .setTitle('Certified Organic')
    .setChoiceValues(['No', 'Yes']);

  form.addMultipleChoiceItem()
    .setTitle('Accepts SNAP / EBT')
    .setChoiceValues(['No', 'Yes']);

  form.addMultipleChoiceItem()
    .setTitle('ADA Accessible')
    .setChoiceValues(['No', 'Yes']);

  form.addParagraphTextItem()
    .setTitle('Where to Get It')
    .setHelpText('Wholesale growers: stores, markets or restaurants that carry your products, one per line (e.g. "Whole Foods Market, Boulder").');

  form.addParagraphTextItem()
    .setTitle('Notes')
    .setHelpText('Anything else we should know? A one-line description works great.');

  // --- Response destination (linked Google Sheet) -----------------------------
  var ss = SpreadsheetApp.create('Colorado Farm Trail — Business Submissions');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // --- Optional: email the maintainer on each submission ----------------------
  if (ENABLE_SUBMIT_NOTIFICATIONS) {
    if (!NOTIFY_EMAIL) {
      throw new Error('ENABLE_SUBMIT_NOTIFICATIONS is true but NOTIFY_EMAIL is empty.');
    }
    ScriptApp.newTrigger('onBusinessFormSubmit')
      .forForm(form)
      .onFormSubmit()
      .create();
  }

  // --- Report the URLs --------------------------------------------------------
  var publishedUrl = form.getPublishedUrl();
  var editUrl = form.getEditUrl();
  var sheetUrl = ss.getUrl();

  Logger.log('PUBLISHED URL (put in index.html button): %s', publishedUrl);
  Logger.log('EDIT URL (put in docs/BUSINESS_SUBMISSIONS.md): %s', editUrl);
  Logger.log('RESPONSES SHEET: %s', sheetUrl);

  return { publishedUrl: publishedUrl, editUrl: editUrl, sheetUrl: sheetUrl };
}

/**
 * Optional submit handler. Only fires if ENABLE_SUBMIT_NOTIFICATIONS was true
 * when createBusinessForm() ran (it installs the trigger). Emails the maintainer
 * a plain-text summary of the new submission.
 */
function onBusinessFormSubmit(e) {
  if (!NOTIFY_EMAIL) return;
  var lines = ['New Colorado Farm Trail business submission:', ''];
  var responses = e.response.getItemResponses();
  for (var i = 0; i < responses.length; i++) {
    var r = responses[i];
    var answer = r.getResponse();
    if (Array.isArray(answer)) answer = answer.join(', ');
    lines.push(r.getItem().getTitle() + ': ' + answer);
  }
  MailApp.sendEmail({
    to: NOTIFY_EMAIL,
    subject: 'New farm/market submission — Colorado Farm Trail',
    body: lines.join('\n')
  });
}
