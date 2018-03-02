const navIcon = document.getElementById('navigationIcon');

let isNavOpen = false,
    nav = document.getElementById('nav');

navIcon.onclick = () => {
    if (window.innerWidth < 500) {
        mobileToggle();
    } else {
        desktopToggle();
    }
}

// $(window).scroll(() => {
//     if ($(window).scrollTop() > 600 && isNavOpen === true) {
//         $(nav).css('display', 'none');
//         isNavOpen = false;
//     }
// })


$('.nav-link').click(() => {
    $(nav).css('display', 'none');
    isNavOpen = false;
});


let desktopToggle = () => {
    if (!isNavOpen) {
        console.log('here');
        $('body').animate({
            scrollTop: 0
        }, 'fast')
        $(nav).slideDown(600);
        isNavOpen = true;
    } else {
        $(nav).slideUp(700);
        isNavOpen = false;
    }
}

let mobileToggle = () => {
    let contentWidth;

    if (!isNavOpen) {
        contentWidth = $('.main-container').width();

        $('.main-container').css('width', contentWidth);


        $(".parent-container").animate({
            "marginLeft": ["-90%"]
        }, {
            duration: 700
        });
        isNavOpen = true;

    } else {
        $('.main-container').unbind('touchmove');

        $(".parent-container").animate({
            "marginLeft": ["0%"]
        }, {
            duration: 700,
            complete: function () {
                $('.main-container').css('width', 'auto');
            }
        });
        isNavOpen = false;
    }

}