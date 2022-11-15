addEventListener('scroll', event => {
   // console.log(window.pageYOffset)
   if (window.pageYOffset >= 20){
      gsap.to('.header', {background: '#00ABB3',duration: 0.3, opacity: 1, ease: 'power1.out', boxShadow: 'rgba(0,0,0,0.3) 0px 1px'})
      gsap.to('.wrapper', {padding: '10px 0', duration: 0.3})
      gsap.to('.logo-text h1', {fontSize: '2.2rem', duration: 0.25, color: "#fff"})
      gsap.to('.btn', {borderRadius: 0, color: '#fff', duration: 0.3})
   }
   else if (window.pageYOffset < 19){
      gsap.to('.header', {background: '#f0f1f3', duration: 0.3, opacity: 1, boxShadow: 'none'})
      gsap.to('.wrapper', {padding: '50px 0', duration: 0.3, ease: 'power1.out'})
      gsap.to('.logo-text h1', {fontSize: '3rem',  color: '#000', duration: 0.3})
      gsap.to('.btn', {borderRadius: '20', color: '#fff', duration: 0.3})
   }
})