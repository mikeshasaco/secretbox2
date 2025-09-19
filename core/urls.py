from django.urls import path
from .controllers import auth as auth_ctrl
from .controllers import pages as pages_ctrl
from .controllers import props as props_ctrl

urlpatterns = [
    path('', pages_ctrl.landing, name='landing'),
    path('week/<int:week>/', pages_ctrl.week_view, name='week'),
    path('game/<str:game_id>/', pages_ctrl.game_detail, name='game_detail'),
    path('game/<str:game_id>/props', props_ctrl.game_props, name='game_props'),
    path('parlay/evaluate', props_ctrl.evaluate_parlay, name='parlay_evaluate'),
    path('login/', auth_ctrl.login_view, name='login'),
    path('logout/', auth_ctrl.logout_view, name='logout'),
    path('signup/', auth_ctrl.signup_view, name='signup'),
]


