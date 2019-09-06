/* global FORM_HANDLERS, $ */

FORM_HANDLERS['registration.von.canada.ca'] = function (form, response) {
  console.log('here')
  if (response.success === true) {
    $(form).find('.legal-entity-id').remove()
    $(form).append(
      `
      <div class="legal-entity-id">
      Your legal entity id is:
      <code>${response.result.claim.legal_entity_id[0]}</code>
      </div>

      `
    )
  }
}

(function($){
  var autocomplete_key = 'UP49-MX76-PT22-ZM49';
  $.typeahead({
    input: '[id$=line1-input]',

    dynamic: true,
    filter: false,
    //display: ['properties.fullAddress'],
    display: ['Text', 'Description'],
    source: {
      sites: {
        ajax: {
          //delay: 150,

          // BC Geocoder
          /*url: 'https://apps.gov.bc.ca/pub/geocoder/addresses.json',
          data: {
            addressString: '{{query}}',
            maxResults: 8,
            interpolation: 'adaptive',
            autoComplete: 'true',
            minScore: 1,
            provinceCode: 'BC',
            echo: true
          },
          path: 'features',*/

          url: 'https://ws1.postescanada-canadapost.ca/AddressComplete/Interactive/AutoComplete/v1.00/json3.ws',
          data: {
            SearchTerm: '{{query}}',
            //Country: 'CAN',
            LanguagePreference: 'EN',
            Key: autocomplete_key
          },
          path: 'Items'
        }
      }
    },
    callback: {
      onInit: function (node) { console.log('ta init', node); },
      onSubmit: function (node, form, item, event) {
        console.log('submit', item);
      },
      onClickAfter (node, a, item, event)	{
        var form = node[0].form;
        var prefix = node[0].name.substring(0, node[0].name.length-14);
        /*var update = {
          // street: fullSiteDescriptor -- civicNumber streetName streetType streetDirection
          // city: item.properties.localityName
        };*/
        if(item.IsRetrievable) {
          $.get('https://ws1.postescanada-canadapost.ca/AddressComplete/Interactive/Retrieve/v1.00/json3.ws',
            {Key: autocomplete_key, Id: item.Id},
            function(data) {
              if(data && data.Items && data.Items.length) {
                var item = data.Items[0]; // [1] for french record
                var upd = {
                  'address_line1': item.Line1,
                  'address_line2': item.Line2,
                  'city': item.City,
                  'province': item.ProvinceCode,
                  'postal_code': item.PostalCode
                };
                for(var k in upd) {
                  var inp = form.elements[prefix + k];
                  if(inp) inp.value = upd[k] || '';
                }
              }
            },
            'json');
        }
      },
      onNavigateBefore: function (node, query, event) {
        if (~[38,40].indexOf(event.keyCode)) {
          event.preventInputChange = true;
        }
      }
    },
    debug: true
  });

})(jQuery);


