$(function() {
  const source = document.getElementById('autoComplete');

  if (source) {
    source.addEventListener('input', function(e) {
      if (typeof window.showAutocompleteSuggestions === 'function') {
        window.showAutocompleteSuggestions();
      }
      $('.movie-button').prop('disabled', e.target.value.trim() === '');
    });

    source.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        window.setTimeout(function() {
          populateInputFromHighlightedAutocomplete(source);
        }, 0);
        return;
      }

      if (e.key === 'Enter') {
        e.preventDefault();
        const title = selectedAutocompleteTitle() || source.value.trim();
        if (title !== '') {
          source.value = title;
          $('.movie-button').prop('disabled', false);
          loadDetails(title);
        }
      }
    });
  }

  $(document).on('click', '.fa-arrow-up', function() {
    $('html, body').animate({scrollTop: 0}, 'slow');
  });

  $('.app-title').click(function() {
    window.location.href = '/';
  });

  $('.movie-button').on('click', function() {
    const title = $('.movie').val().trim();
    if (title === '') {
      $('.results').css('display', 'none');
      $('.fail').css('display', 'block');
      dismissAutocomplete();
      return;
    }

    loadDetails(title);
  });
});

function recommendcard(e) {
  const title = e.getAttribute('title');
  loadDetails(title);
}

function loadDetails(title) {
  title = (title || '').trim();
  if (title === '') {
    return;
  }

  dismissAutocomplete();
  $('.movie-button').prop('disabled', true);
  $("#loader").stop(true, true).fadeIn();
  $('.fail').css('display', 'none');
  $('.results').css('display', 'block');

  $.ajax({
    type: 'POST',
    data: {title: title},
    url: '/recommend',
    dataType: 'html',
    complete: function() {
      $("#loader").delay(300).fadeOut();
    },
    success: function(response) {
      $('.results').html(response);
      $('.dataset-note').fadeOut(150);
      $('#autoComplete').val('');
      $('.movie-button').prop('disabled', true);
      $('.footer').css('position', 'absolute');

      if ($('.movie-content').length && $('.gototop').length === 0) {
        $('.movie-content').last().after('<div class="gototop"><i title="Go to Top" class="fa fa-arrow-up"></i></div>');
      }

      window.scrollTo({top: 0, behavior: 'auto'});
    },
    error: function(response) {
      $('.results').html(response.responseText);
      $('.fail').css('display', 'none');
      $('#autoComplete').val(title);
      $('.movie-button').prop('disabled', false);
      dismissAutocomplete();
    }
  });
}

function dismissAutocomplete() {
  if (typeof window.clearAutocompleteSuggestions === 'function') {
    window.clearAutocompleteSuggestions();
  }

  $('#autoComplete_list, #food_list, .autoComplete_list').empty().hide();
  $('#autoComplete').attr('aria-expanded', 'false').blur();
}

function selectedAutocompleteTitle() {
  const selectors = [
    '#autoComplete_list [aria-selected="true"]',
    '#food_list [aria-selected="true"]',
    '#autoComplete_list .autoComplete_selected',
    '#food_list .autoComplete_selected',
    '#autoComplete_list .selected',
    '#food_list .selected',
    '#autoComplete_list .active',
    '#food_list .active',
    '#autoComplete_list li:focus',
    '#food_list li:focus'
  ];

  for (const selector of selectors) {
    const item = document.querySelector(selector);
    const title = cleanAutocompleteTitle(item);
    if (title) {
      return title;
    }
  }

  return '';
}

function populateInputFromHighlightedAutocomplete(source) {
  const title = selectedAutocompleteTitle();
  if (!title) {
    return;
  }

  source.value = title;
  $('.movie-button').prop('disabled', false);
}

function cleanAutocompleteTitle(item) {
  if (!item) {
    return '';
  }

  const title = item.textContent.replace(/\s+/g, ' ').trim();
  return title === 'No Results' ? '' : title;
}
