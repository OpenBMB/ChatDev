#################################### IMPORTS ###################################


import unittest

import pygame
from pygame import sprite


################################# MODULE LEVEL #################################


class SpriteModuleTest(unittest.TestCase):
    pass


######################### SPRITECOLLIDE FUNCTIONS TEST #########################


class SpriteCollideTest(unittest.TestCase):
    def setUp(self):
        self.ag = sprite.AbstractGroup()
        self.ag2 = sprite.AbstractGroup()
        self.s1 = sprite.Sprite(self.ag)
        self.s2 = sprite.Sprite(self.ag2)
        self.s3 = sprite.Sprite(self.ag2)

        self.s1.image = pygame.Surface((50, 10), pygame.SRCALPHA, 32)
        self.s2.image = pygame.Surface((10, 10), pygame.SRCALPHA, 32)
        self.s3.image = pygame.Surface((10, 10), pygame.SRCALPHA, 32)

        self.s1.rect = self.s1.image.get_rect()
        self.s2.rect = self.s2.image.get_rect()
        self.s3.rect = self.s3.image.get_rect()
        self.s2.rect.move_ip(40, 0)
        self.s3.rect.move_ip(100, 100)

    def test_spritecollide__works_if_collided_cb_is_None(self):
        # Test that sprites collide without collided function.
        self.assertEqual(
            sprite.spritecollide(self.s1, self.ag2, dokill=False, collided=None),
            [self.s2],
        )

    def test_spritecollide__works_if_collided_cb_not_passed(self):
        # Should also work when collided function isn't passed at all.
        self.assertEqual(
            sprite.spritecollide(self.s1, self.ag2, dokill=False), [self.s2]
        )

    def test_spritecollide__collided_must_be_a_callable(self):
        # Need to pass a callable.
        self.assertRaises(
            TypeError, sprite.spritecollide, self.s1, self.ag2, dokill=False, collided=1
        )

    def test_spritecollide__collided_defaults_to_collide_rect(self):
        # collide_rect should behave the same as default.
        self.assertEqual(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_rect
            ),
            [self.s2],
        )

    def test_collide_rect_ratio__ratio_of_one_like_default(self):
        # collide_rect_ratio should behave the same as default at a 1.0 ratio.
        self.assertEqual(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_rect_ratio(1.0)
            ),
            [self.s2],
        )

    def test_collide_rect_ratio__collides_all_at_ratio_of_twenty(self):
        # collide_rect_ratio should collide all at a 20.0 ratio.
        collided_func = sprite.collide_rect_ratio(20.0)
        expected_sprites = sorted(self.ag2.sprites(), key=id)

        collided_sprites = sorted(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=collided_func
            ),
            key=id,
        )

        self.assertListEqual(collided_sprites, expected_sprites)

    def test_collide_circle__no_radius_set(self):
        # collide_circle with no radius set.
        self.assertEqual(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_circle
            ),
            [self.s2],
        )

    def test_collide_circle_ratio__no_radius_and_ratio_of_one(self):
        # collide_circle_ratio with no radius set, at a 1.0 ratio.
        self.assertEqual(
            sprite.spritecollide(
                self.s1,
                self.ag2,
                dokill=False,
                collided=sprite.collide_circle_ratio(1.0),
            ),
            [self.s2],
        )

    def test_collide_circle_ratio__no_radius_and_ratio_of_twenty(self):
        # collide_circle_ratio with no radius set, at a 20.0 ratio.
        collided_func = sprite.collide_circle_ratio(20.0)
        expected_sprites = sorted(self.ag2.sprites(), key=id)

        collided_sprites = sorted(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=collided_func
            ),
            key=id,
        )

        self.assertListEqual(expected_sprites, collided_sprites)

    def test_collide_circle__radius_set_by_collide_circle_ratio(self):
        # Call collide_circle_ratio with no radius set, at a 20.0 ratio.
        # That should return group ag2 AND set the radius attribute of the
        # sprites in such a way that collide_circle would give same result as
        # if it had been called without the radius being set.
        collided_func = sprite.collide_circle_ratio(20.0)

        sprite.spritecollide(self.s1, self.ag2, dokill=False, collided=collided_func)

        self.assertEqual(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_circle
            ),
            [self.s2],
        )

    def test_collide_circle_ratio__no_radius_and_ratio_of_two_twice(self):
        # collide_circle_ratio with no radius set, at a 2.0 ratio,
        # called twice to check if the bug where the calculated radius
        # is not stored correctly in the radius attribute of each sprite.
        collided_func = sprite.collide_circle_ratio(2.0)

        # Calling collide_circle_ratio will set the radius attribute of the
        # sprites. If an incorrect value is stored then we will not get the
        # same result next time it is called:
        expected_sprites = sorted(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=collided_func
            ),
            key=id,
        )
        collided_sprites = sorted(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=collided_func
            ),
            key=id,
        )

        self.assertListEqual(expected_sprites, collided_sprites)

    def test_collide_circle__with_radii_set(self):
        # collide_circle with a radius set.
        self.s1.radius = 50
        self.s2.radius = 10
        self.s3.radius = 400
        collided_func = sprite.collide_circle
        expected_sprites = sorted(self.ag2.sprites(), key=id)

        collided_sprites = sorted(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=collided_func
            ),
            key=id,
        )

        self.assertListEqual(expected_sprites, collided_sprites)

    def test_collide_circle_ratio__with_radii_set(self):
        # collide_circle_ratio with a radius set.
        self.s1.radius = 50
        self.s2.radius = 10
        self.s3.radius = 400
        collided_func = sprite.collide_circle_ratio(0.5)
        expected_sprites = sorted(self.ag2.sprites(), key=id)

        collided_sprites = sorted(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=collided_func
            ),
            key=id,
        )

        self.assertListEqual(expected_sprites, collided_sprites)

    def test_collide_mask__opaque(self):
        # make some fully opaque sprites that will collide with masks.
        self.s1.image.fill((255, 255, 255, 255))
        self.s2.image.fill((255, 255, 255, 255))
        self.s3.image.fill((255, 255, 255, 255))

        # masks should be autogenerated from image if they don't exist.
        self.assertEqual(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_mask
            ),
            [self.s2],
        )

        self.s1.mask = pygame.mask.from_surface(self.s1.image)
        self.s2.mask = pygame.mask.from_surface(self.s2.image)
        self.s3.mask = pygame.mask.from_surface(self.s3.image)

        # with set masks.
        self.assertEqual(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_mask
            ),
            [self.s2],
        )

    def test_collide_mask__transparent(self):
        # make some sprites that are fully transparent, so they won't collide.
        self.s1.image.fill((255, 255, 255, 0))
        self.s2.image.fill((255, 255, 255, 0))
        self.s3.image.fill((255, 255, 255, 0))

        self.s1.mask = pygame.mask.from_surface(self.s1.image, 255)
        self.s2.mask = pygame.mask.from_surface(self.s2.image, 255)
        self.s3.mask = pygame.mask.from_surface(self.s3.image, 255)

        self.assertFalse(
            sprite.spritecollide(
                self.s1, self.ag2, dokill=False, collided=sprite.collide_mask
            )
        )

    def test_spritecollideany__without_collided_callback(self):
        # pygame.sprite.spritecollideany(sprite, group) -> sprite
        # finds any sprites that collide

        # if collided is not passed, all
        # sprites must have a "rect" value, which is a
        # rectangle of the sprite area, which will be used
        # to calculate the collision.

        # s2 in, s3 out
        expected_sprite = self.s2
        collided_sprite = sprite.spritecollideany(self.s1, self.ag2)

        self.assertEqual(collided_sprite, expected_sprite)

        # s2 and s3 out
        self.s2.rect.move_ip(0, 10)
        collided_sprite = sprite.spritecollideany(self.s1, self.ag2)

        self.assertIsNone(collided_sprite)

        # s2 out, s3 in
        self.s3.rect.move_ip(-105, -105)
        expected_sprite = self.s3
        collided_sprite = sprite.spritecollideany(self.s1, self.ag2)

        self.assertEqual(collided_sprite, expected_sprite)

        # s2 and s3 in
        self.s2.rect.move_ip(0, -10)
        expected_sprite_choices = self.ag2.sprites()
        collided_sprite = sprite.spritecollideany(self.s1, self.ag2)

        self.assertIn(collided_sprite, expected_sprite_choices)

    def test_spritecollideany__with_collided_callback(self):
        # pygame.sprite.spritecollideany(sprite, group) -> sprite
        # finds any sprites that collide

        # collided is a callback function used to calculate if
        # two sprites are colliding. it should take two sprites
        # as values, and return a bool value indicating if
        # they are colliding.

        # This collision test can be faster than pygame.sprite.spritecollide()
        # since it has less work to do.

        arg_dict_a = {}
        arg_dict_b = {}
        return_container = [True]

        # This function is configurable using the mutable default arguments!
        def collided_callback(
            spr_a,
            spr_b,
            arg_dict_a=arg_dict_a,
            arg_dict_b=arg_dict_b,
            return_container=return_container,
        ):
            count = arg_dict_a.get(spr_a, 0)
            arg_dict_a[spr_a] = 1 + count

            count = arg_dict_b.get(spr_b, 0)
            arg_dict_b[spr_b] = 1 + count

            return return_container[0]

        # This should return a sprite from self.ag2 because the callback
        # function (collided_callback()) currently returns True.
        expected_sprite_choices = self.ag2.sprites()
        collided_sprite = sprite.spritecollideany(self.s1, self.ag2, collided_callback)

        self.assertIn(collided_sprite, expected_sprite_choices)

        # The callback function should have been called only once, so self.s1
        # should have only been passed as an argument once
        self.assertEqual(len(arg_dict_a), 1)
        self.assertEqual(arg_dict_a[self.s1], 1)

        # The callback function should have been called only once, so self.s2
        # exclusive-or self.s3 should have only been passed as an argument
        # once
        self.assertEqual(len(arg_dict_b), 1)
        self.assertEqual(list(arg_dict_b.values())[0], 1)
        self.assertTrue(self.s2 in arg_dict_b or self.s3 in arg_dict_b)

        arg_dict_a.clear()
        arg_dict_b.clear()
        return_container[0] = False

        # This should return None because the callback function
        # (collided_callback()) currently returns False.
        collided_sprite = sprite.spritecollideany(self.s1, self.ag2, collided_callback)

        self.assertIsNone(collided_sprite)

        # The callback function should have been called as many times as
        # there are sprites in self.ag2
        self.assertEqual(len(arg_dict_a), 1)
        self.assertEqual(arg_dict_a[self.s1], len(self.ag2))
        self.assertEqual(len(arg_dict_b), len(self.ag2))

        # Each sprite in self.ag2 should be called once.
        for s in self.ag2:
            self.assertEqual(arg_dict_b[s], 1)

    def test_groupcollide__without_collided_callback(self):
        # pygame.sprite.groupcollide(groupa, groupb, dokilla, dokillb) -> dict
        # collision detection between group and group

        # test no kill
        expected_dict = {self.s1: [self.s2]}
        crashed = pygame.sprite.groupcollide(self.ag, self.ag2, False, False)

        self.assertDictEqual(expected_dict, crashed)

        crashed = pygame.sprite.groupcollide(self.ag, self.ag2, False, False)

        self.assertDictEqual(expected_dict, crashed)

        # Test dokill2=True (kill colliding sprites in second group).
        crashed = pygame.sprite.groupcollide(self.ag, self.ag2, False, True)

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {}
        crashed = pygame.sprite.groupcollide(self.ag, self.ag2, False, False)

        self.assertDictEqual(expected_dict, crashed)

        # Test dokill1=True (kill colliding sprites in first group).
        self.s3.rect.move_ip(-100, -100)
        expected_dict = {self.s1: [self.s3]}
        crashed = pygame.sprite.groupcollide(self.ag, self.ag2, True, False)

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {}
        crashed = pygame.sprite.groupcollide(self.ag, self.ag2, False, False)

        self.assertDictEqual(expected_dict, crashed)

    def test_groupcollide__with_collided_callback(self):
        collided_callback_true = lambda spr_a, spr_b: True
        collided_callback_false = lambda spr_a, spr_b: False

        # test no kill
        expected_dict = {}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, False, False, collided_callback_false
        )

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {self.s1: sorted(self.ag2.sprites(), key=id)}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, False, False, collided_callback_true
        )
        for value in crashed.values():
            value.sort(key=id)

        self.assertDictEqual(expected_dict, crashed)

        # expected_dict is the same again for this collide
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, False, False, collided_callback_true
        )
        for value in crashed.values():
            value.sort(key=id)

        self.assertDictEqual(expected_dict, crashed)

        # Test dokill2=True (kill colliding sprites in second group).
        expected_dict = {}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, False, True, collided_callback_false
        )

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {self.s1: sorted(self.ag2.sprites(), key=id)}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, False, True, collided_callback_true
        )
        for value in crashed.values():
            value.sort(key=id)

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, False, True, collided_callback_true
        )

        self.assertDictEqual(expected_dict, crashed)

        # Test dokill1=True (kill colliding sprites in first group).
        self.ag.add(self.s2)
        self.ag2.add(self.s3)
        expected_dict = {}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, True, False, collided_callback_false
        )

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {self.s1: [self.s3], self.s2: [self.s3]}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, True, False, collided_callback_true
        )

        self.assertDictEqual(expected_dict, crashed)

        expected_dict = {}
        crashed = pygame.sprite.groupcollide(
            self.ag, self.ag2, True, False, collided_callback_true
        )

        self.assertDictEqual(expected_dict, crashed)

    def test_collide_rect(self):
        # Test colliding - some edges touching
        self.assertTrue(pygame.sprite.collide_rect(self.s1, self.s2))
        self.assertTrue(pygame.sprite.collide_rect(self.s2, self.s1))

        # Test colliding - all edges touching
        self.s2.rect.center = self.s3.rect.center

        self.assertTrue(pygame.sprite.collide_rect(self.s2, self.s3))
        self.assertTrue(pygame.sprite.collide_rect(self.s3, self.s2))

        # Test colliding - no edges touching
        self.s2.rect.inflate_ip(10, 10)

        self.assertTrue(pygame.sprite.collide_rect(self.s2, self.s3))
        self.assertTrue(pygame.sprite.collide_rect(self.s3, self.s2))

        # Test colliding - some edges intersecting
        self.s2.rect.center = (self.s1.rect.right, self.s1.rect.bottom)

        self.assertTrue(pygame.sprite.collide_rect(self.s1, self.s2))
        self.assertTrue(pygame.sprite.collide_rect(self.s2, self.s1))

        # Test not colliding
        self.assertFalse(pygame.sprite.collide_rect(self.s1, self.s3))
        self.assertFalse(pygame.sprite.collide_rect(self.s3, self.s1))


################################################################################


class AbstractGroupTypeTest(unittest.TestCase):
    def setUp(self):
        self.ag = sprite.AbstractGroup()
        self.ag2 = sprite.AbstractGroup()
        self.s1 = sprite.Sprite(self.ag)
        self.s2 = sprite.Sprite(self.ag)
        self.s3 = sprite.Sprite(self.ag2)
        self.s4 = sprite.Sprite(self.ag2)

        self.s1.image = pygame.Surface((10, 10))
        self.s1.image.fill(pygame.Color("red"))
        self.s1.rect = self.s1.image.get_rect()

        self.s2.image = pygame.Surface((10, 10))
        self.s2.image.fill(pygame.Color("green"))
        self.s2.rect = self.s2.image.get_rect()
        self.s2.rect.left = 10

        self.s3.image = pygame.Surface((10, 10))
        self.s3.image.fill(pygame.Color("blue"))
        self.s3.rect = self.s3.image.get_rect()
        self.s3.rect.top = 10

        self.s4.image = pygame.Surface((10, 10))
        self.s4.image.fill(pygame.Color("white"))
        self.s4.rect = self.s4.image.get_rect()
        self.s4.rect.left = 10
        self.s4.rect.top = 10

        self.bg = pygame.Surface((20, 20))
        self.scr = pygame.Surface((20, 20))
        self.scr.fill(pygame.Color("grey"))

    def test_has(self):
        "See if AbstractGroup.has() works as expected."

        self.assertEqual(True, self.s1 in self.ag)

        self.assertEqual(True, self.ag.has(self.s1))

        self.assertEqual(True, self.ag.has([self.s1, self.s2]))

        # see if one of them not being in there.
        self.assertNotEqual(True, self.ag.has([self.s1, self.s2, self.s3]))
        self.assertNotEqual(True, self.ag.has(self.s1, self.s2, self.s3))
        self.assertNotEqual(True, self.ag.has(self.s1, sprite.Group(self.s2, self.s3)))
        self.assertNotEqual(True, self.ag.has(self.s1, [self.s2, self.s3]))

        # test empty list processing
        self.assertFalse(self.ag.has(*[]))
        self.assertFalse(self.ag.has([]))
        self.assertFalse(self.ag.has([[]]))

        # see if a second AbstractGroup works.
        self.assertEqual(True, self.ag2.has(self.s3))

    def test_add(self):
        ag3 = sprite.AbstractGroup()
        sprites = (self.s1, self.s2, self.s3, self.s4)

        for s in sprites:
            self.assertNotIn(s, ag3)

        ag3.add(self.s1, [self.s2], self.ag2)

        for s in sprites:
            self.assertIn(s, ag3)

    def test_add_internal(self):
        self.assertNotIn(self.s1, self.ag2)

        self.ag2.add_internal(self.s1)

        self.assertIn(self.s1, self.ag2)

    def test_clear(self):
        self.ag.draw(self.scr)
        self.ag.clear(self.scr, self.bg)
        self.assertEqual((0, 0, 0, 255), self.scr.get_at((5, 5)))
        self.assertEqual((0, 0, 0, 255), self.scr.get_at((15, 5)))

    def test_draw(self):
        self.ag.draw(self.scr)
        self.assertEqual((255, 0, 0, 255), self.scr.get_at((5, 5)))
        self.assertEqual((0, 255, 0, 255), self.scr.get_at((15, 5)))

        self.assertEqual(self.ag.spritedict[self.s1], pygame.Rect(0, 0, 10, 10))
        self.assertEqual(self.ag.spritedict[self.s2], pygame.Rect(10, 0, 10, 10))

    def test_empty(self):
        self.ag.empty()
        self.assertFalse(self.s1 in self.ag)
        self.assertFalse(self.s2 in self.ag)

    def test_has_internal(self):
        self.assertTrue(self.ag.has_internal(self.s1))
        self.assertFalse(self.ag.has_internal(self.s3))

    def test_remove(self):
        # Test removal of 1 sprite
        self.ag.remove(self.s1)
        self.assertFalse(self.ag in self.s1.groups())
        self.assertFalse(self.ag.has(self.s1))

        # Test removal of 2 sprites as 2 arguments
        self.ag2.remove(self.s3, self.s4)
        self.assertFalse(self.ag2 in self.s3.groups())
        self.assertFalse(self.ag2 in self.s4.groups())
        self.assertFalse(self.ag2.has(self.s3, self.s4))

        # Test removal of 4 sprites as a list containing a sprite and a group
        # containing a sprite and another group containing 2 sprites.
        self.ag.add(self.s1, self.s3, self.s4)
        self.ag2.add(self.s3, self.s4)
        g = sprite.Group(self.s2)
        self.ag.remove([self.s1, g], self.ag2)
        self.assertFalse(self.ag in self.s1.groups())
        self.assertFalse(self.ag in self.s2.groups())
        self.assertFalse(self.ag in self.s3.groups())
        self.assertFalse(self.ag in self.s4.groups())
        self.assertFalse(self.ag.has(self.s1, self.s2, self.s3, self.s4))

    def test_remove_internal(self):
        self.ag.remove_internal(self.s1)
        self.assertFalse(self.ag.has_internal(self.s1))

    def test_sprites(self):
        expected_sprites = sorted((self.s1, self.s2), key=id)
        sprite_list = sorted(self.ag.sprites(), key=id)

        self.assertListEqual(sprite_list, expected_sprites)

    def test_update(self):
        class test_sprite(pygame.sprite.Sprite):
            sink = []

            def __init__(self, *groups):
                pygame.sprite.Sprite.__init__(self, *groups)

            def update(self, *args):
                self.sink += args

        s = test_sprite(self.ag)
        self.ag.update(1, 2, 3)

        self.assertEqual(test_sprite.sink, [1, 2, 3])

    def test_update_with_kwargs(self):
        class test_sprite(pygame.sprite.Sprite):
            sink = []
            sink_kwargs = {}

            def __init__(self, *groups):
                pygame.sprite.Sprite.__init__(self, *groups)

            def update(self, *args, **kwargs):
                self.sink += args
                self.sink_kwargs.update(kwargs)

        s = test_sprite(self.ag)
        self.ag.update(1, 2, 3, foo=4, bar=5)

        self.assertEqual(test_sprite.sink, [1, 2, 3])
        self.assertEqual(test_sprite.sink_kwargs, {"foo": 4, "bar": 5})


################################################################################

# A base class to share tests between similar classes


class LayeredGroupBase:
    def test_get_layer_of_sprite(self):
        expected_layer = 666
        spr = self.sprite()
        self.LG.add(spr, layer=expected_layer)
        layer = self.LG.get_layer_of_sprite(spr)

        self.assertEqual(len(self.LG._spritelist), 1)
        self.assertEqual(layer, self.LG.get_layer_of_sprite(spr))
        self.assertEqual(layer, expected_layer)
        self.assertEqual(layer, self.LG._spritelayers[spr])

    def test_add(self):
        expected_layer = self.LG._default_layer
        spr = self.sprite()
        self.LG.add(spr)
        layer = self.LG.get_layer_of_sprite(spr)

        self.assertEqual(len(self.LG._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__sprite_with_layer_attribute(self):
        expected_layer = 100
        spr = self.sprite()
        spr._layer = expected_layer
        self.LG.add(spr)
        layer = self.LG.get_layer_of_sprite(spr)

        self.assertEqual(len(self.LG._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__passing_layer_keyword(self):
        expected_layer = 100
        spr = self.sprite()
        self.LG.add(spr, layer=expected_layer)
        layer = self.LG.get_layer_of_sprite(spr)

        self.assertEqual(len(self.LG._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__overriding_sprite_layer_attr(self):
        expected_layer = 200
        spr = self.sprite()
        spr._layer = 100
        self.LG.add(spr, layer=expected_layer)
        layer = self.LG.get_layer_of_sprite(spr)

        self.assertEqual(len(self.LG._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__adding_sprite_on_init(self):
        spr = self.sprite()
        lrg2 = sprite.LayeredUpdates(spr)
        expected_layer = lrg2._default_layer
        layer = lrg2._spritelayers[spr]

        self.assertEqual(len(lrg2._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__sprite_init_layer_attr(self):
        expected_layer = 20
        spr = self.sprite()
        spr._layer = expected_layer
        lrg2 = sprite.LayeredUpdates(spr)
        layer = lrg2._spritelayers[spr]

        self.assertEqual(len(lrg2._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__sprite_init_passing_layer(self):
        expected_layer = 33
        spr = self.sprite()
        lrg2 = sprite.LayeredUpdates(spr, layer=expected_layer)
        layer = lrg2._spritelayers[spr]

        self.assertEqual(len(lrg2._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__sprite_init_overiding_layer(self):
        expected_layer = 33
        spr = self.sprite()
        spr._layer = 55
        lrg2 = sprite.LayeredUpdates(spr, layer=expected_layer)
        layer = lrg2._spritelayers[spr]

        self.assertEqual(len(lrg2._spritelist), 1)
        self.assertEqual(layer, expected_layer)

    def test_add__spritelist(self):
        expected_layer = self.LG._default_layer
        sprite_count = 10
        sprites = [self.sprite() for _ in range(sprite_count)]

        self.LG.add(sprites)

        self.assertEqual(len(self.LG._spritelist), sprite_count)

        for i in range(sprite_count):
            layer = self.LG.get_layer_of_sprite(sprites[i])

            self.assertEqual(layer, expected_layer)

    def test_add__spritelist_with_layer_attr(self):
        sprites = []
        sprite_and_layer_count = 10
        for i in range(sprite_and_layer_count):
            sprites.append(self.sprite())
            sprites[-1]._layer = i

        self.LG.add(sprites)

        self.assertEqual(len(self.LG._spritelist), sprite_and_layer_count)

        for i in range(sprite_and_layer_count):
            layer = self.LG.get_layer_of_sprite(sprites[i])

            self.assertEqual(layer, i)

    def test_add__spritelist_passing_layer(self):
        expected_layer = 33
        sprite_count = 10
        sprites = [self.sprite() for _ in range(sprite_count)]

        self.LG.add(sprites, layer=expected_layer)

        self.assertEqual(len(self.LG._spritelist), sprite_count)

        for i in range(sprite_count):
            layer = self.LG.get_layer_of_sprite(sprites[i])

            self.assertEqual(layer, expected_layer)

    def test_add__spritelist_overriding_layer(self):
        expected_layer = 33
        sprites = []
        sprite_and_layer_count = 10
        for i in range(sprite_and_layer_count):
            sprites.append(self.sprite())
            sprites[-1].layer = i

        self.LG.add(sprites, layer=expected_layer)

        self.assertEqual(len(self.LG._spritelist), sprite_and_layer_count)

        for i in range(sprite_and_layer_count):
            layer = self.LG.get_layer_of_sprite(sprites[i])

            self.assertEqual(layer, expected_layer)

    def test_add__spritelist_init(self):
        sprite_count = 10
        sprites = [self.sprite() for _ in range(sprite_count)]

        lrg2 = sprite.LayeredUpdates(sprites)
        expected_layer = lrg2._default_layer

        self.assertEqual(len(lrg2._spritelist), sprite_count)

        for i in range(sprite_count):
            layer = lrg2.get_layer_of_sprite(sprites[i])

            self.assertEqual(layer, expected_layer)

    def test_remove__sprite(self):
        sprites = []
        sprite_count = 10
        for i in range(sprite_count):
            sprites.append(self.sprite())
            sprites[-1].rect = pygame.Rect((0, 0, 0, 0))

        self.LG.add(sprites)

        self.assertEqual(len(self.LG._spritelist), sprite_count)

        for i in range(sprite_count):
            self.LG.remove(sprites[i])

        self.assertEqual(len(self.LG._spritelist), 0)

    def test_sprites(self):
        sprites = []
        sprite_and_layer_count = 10
        for i in range(sprite_and_layer_count, 0, -1):
            sprites.append(self.sprite())
            sprites[-1]._layer = i

        self.LG.add(sprites)

        self.assertEqual(len(self.LG._spritelist), sprite_and_layer_count)

        # Sprites should be ordered based on their layer (bottom to top),
        # which is the reverse order of the sprites list.
        expected_sprites = list(reversed(sprites))
        actual_sprites = self.LG.sprites()

        self.assertListEqual(actual_sprites, expected_sprites)

    def test_layers(self):
        sprites = []
        expected_layers = []
        layer_count = 10
        for i in range(layer_count):
            expected_layers.append(i)
            for j in range(5):
                sprites.append(self.sprite())
                sprites[-1]._layer = i
        self.LG.add(sprites)

        layers = self.LG.layers()

        self.assertListEqual(layers, expected_layers)

    def test_add__layers_are_correct(self):
        layers = [1, 4, 6, 8, 3, 6, 2, 6, 4, 5, 6, 1, 0, 9, 7, 6, 54, 8, 2, 43, 6, 1]
        for lay in layers:
            self.LG.add(self.sprite(), layer=lay)
        layers.sort()

        for idx, spr in enumerate(self.LG.sprites()):
            layer = self.LG.get_layer_of_sprite(spr)

            self.assertEqual(layer, layers[idx])

    def test_change_layer(self):
        expected_layer = 99
        spr = self.sprite()
        self.LG.add(spr, layer=expected_layer)

        self.assertEqual(self.LG._spritelayers[spr], expected_layer)

        expected_layer = 44
        self.LG.change_layer(spr, expected_layer)

        self.assertEqual(self.LG._spritelayers[spr], expected_layer)

        expected_layer = 77
        spr2 = self.sprite()
        spr2.layer = 55
        self.LG.add(spr2)
        self.LG.change_layer(spr2, expected_layer)

        self.assertEqual(spr2.layer, expected_layer)

    def test_get_sprites_at(self):
        sprites = []
        expected_sprites = []
        for i in range(3):
            spr = self.sprite()
            spr.rect = pygame.Rect(i * 50, i * 50, 100, 100)
            sprites.append(spr)
            if i < 2:
                expected_sprites.append(spr)
        self.LG.add(sprites)
        result = self.LG.get_sprites_at((50, 50))
        self.assertEqual(result, expected_sprites)

    def test_get_top_layer(self):
        layers = [1, 5, 2, 8, 4, 5, 3, 88, 23, 0]
        for i in layers:
            self.LG.add(self.sprite(), layer=i)
        top_layer = self.LG.get_top_layer()

        self.assertEqual(top_layer, self.LG.get_top_layer())
        self.assertEqual(top_layer, max(layers))
        self.assertEqual(top_layer, max(self.LG._spritelayers.values()))
        self.assertEqual(top_layer, self.LG._spritelayers[self.LG._spritelist[-1]])

    def test_get_bottom_layer(self):
        layers = [1, 5, 2, 8, 4, 5, 3, 88, 23, 0]
        for i in layers:
            self.LG.add(self.sprite(), layer=i)
        bottom_layer = self.LG.get_bottom_layer()

        self.assertEqual(bottom_layer, self.LG.get_bottom_layer())
        self.assertEqual(bottom_layer, min(layers))
        self.assertEqual(bottom_layer, min(self.LG._spritelayers.values()))
        self.assertEqual(bottom_layer, self.LG._spritelayers[self.LG._spritelist[0]])

    def test_move_to_front(self):
        layers = [1, 5, 2, 8, 4, 5, 3, 88, 23, 0]
        for i in layers:
            self.LG.add(self.sprite(), layer=i)
        spr = self.sprite()
        self.LG.add(spr, layer=3)

        self.assertNotEqual(spr, self.LG._spritelist[-1])

        self.LG.move_to_front(spr)

        self.assertEqual(spr, self.LG._spritelist[-1])

    def test_move_to_back(self):
        layers = [1, 5, 2, 8, 4, 5, 3, 88, 23, 0]
        for i in layers:
            self.LG.add(self.sprite(), layer=i)
        spr = self.sprite()
        self.LG.add(spr, layer=55)

        self.assertNotEqual(spr, self.LG._spritelist[0])

        self.LG.move_to_back(spr)

        self.assertEqual(spr, self.LG._spritelist[0])

    def test_get_top_sprite(self):
        layers = [1, 5, 2, 8, 4, 5, 3, 88, 23, 0]
        for i in layers:
            self.LG.add(self.sprite(), layer=i)
        expected_layer = self.LG.get_top_layer()
        layer = self.LG.get_layer_of_sprite(self.LG.get_top_sprite())

        self.assertEqual(layer, expected_layer)

    def test_get_sprites_from_layer(self):
        sprites = {}
        layers = [
            1,
            4,
            5,
            6,
            3,
            7,
            8,
            2,
            1,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            0,
            1,
            6,
            5,
            4,
            3,
            2,
        ]
        for lay in layers:
            spr = self.sprite()
            spr._layer = lay
            self.LG.add(spr)
            if lay not in sprites:
                sprites[lay] = []
            sprites[lay].append(spr)

        for lay in self.LG.layers():
            for spr in self.LG.get_sprites_from_layer(lay):
                self.assertIn(spr, sprites[lay])

                sprites[lay].remove(spr)
                if len(sprites[lay]) == 0:
                    del sprites[lay]

        self.assertEqual(len(sprites.values()), 0)

    def test_switch_layer(self):
        sprites1 = []
        sprites2 = []
        layers = [3, 2, 3, 2, 3, 3, 2, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 3, 2, 2, 3, 2, 3]
        for lay in layers:
            spr = self.sprite()
            spr._layer = lay
            self.LG.add(spr)
            if lay == 2:
                sprites1.append(spr)
            else:
                sprites2.append(spr)

        sprites1.sort(key=id)
        sprites2.sort(key=id)
        layer2_sprites = sorted(self.LG.get_sprites_from_layer(2), key=id)
        layer3_sprites = sorted(self.LG.get_sprites_from_layer(3), key=id)

        self.assertListEqual(sprites1, layer2_sprites)
        self.assertListEqual(sprites2, layer3_sprites)
        self.assertEqual(len(self.LG), len(sprites1) + len(sprites2))

        self.LG.switch_layer(2, 3)
        layer2_sprites = sorted(self.LG.get_sprites_from_layer(2), key=id)
        layer3_sprites = sorted(self.LG.get_sprites_from_layer(3), key=id)

        self.assertListEqual(sprites1, layer3_sprites)
        self.assertListEqual(sprites2, layer2_sprites)
        self.assertEqual(len(self.LG), len(sprites1) + len(sprites2))

    def test_copy(self):
        self.LG.add(self.sprite())
        spr = self.LG.sprites()[0]
        lg_copy = self.LG.copy()

        self.assertIsInstance(lg_copy, type(self.LG))
        self.assertIn(spr, lg_copy)
        self.assertIn(lg_copy, spr.groups())


########################## LAYERED RENDER GROUP TESTS ##########################


class LayeredUpdatesTypeTest__SpriteTest(LayeredGroupBase, unittest.TestCase):
    sprite = sprite.Sprite

    def setUp(self):
        self.LG = sprite.LayeredUpdates()


class LayeredUpdatesTypeTest__DirtySprite(LayeredGroupBase, unittest.TestCase):
    sprite = sprite.DirtySprite

    def setUp(self):
        self.LG = sprite.LayeredUpdates()


class LayeredDirtyTypeTest__DirtySprite(LayeredGroupBase, unittest.TestCase):
    sprite = sprite.DirtySprite

    def setUp(self):
        self.LG = sprite.LayeredDirty()

    def test_repaint_rect(self):
        group = self.LG
        surface = pygame.Surface((100, 100))

        group.repaint_rect(pygame.Rect(0, 0, 100, 100))
        group.draw(surface)

    def test_repaint_rect_with_clip(self):
        group = self.LG
        surface = pygame.Surface((100, 100))

        group.set_clip(pygame.Rect(0, 0, 100, 100))
        group.repaint_rect(pygame.Rect(0, 0, 100, 100))
        group.draw(surface)

    def _nondirty_intersections_redrawn(self, use_source_rect=False):
        # Helper method to ensure non-dirty sprites are redrawn correctly.
        #
        # Parameters:
        #     use_source_rect - allows non-dirty sprites to be tested
        #         with (True) and without (False) a source_rect
        #
        # This test was written to reproduce the behavior seen in issue #898.
        # A non-dirty sprite (using source_rect) was being redrawn incorrectly
        # after a dirty sprite intersected with it.
        #
        # This test does the following.
        # 1. Creates a surface filled with white. Also creates an image_source
        #    with a default fill color of yellow and adds 2 images to it
        #    (red and blue rectangles).
        # 2. Creates 2 DirtySprites (red_sprite and blue_sprite) using the
        #    image_source and adds them to a LayeredDirty group.
        # 3. Moves the red_sprite and calls LayeredDirty.draw(surface) a few
        #    times.
        # 4. Checks to make sure the sprites were redrawn correctly.
        RED = pygame.Color("red")
        BLUE = pygame.Color("blue")
        WHITE = pygame.Color("white")
        YELLOW = pygame.Color("yellow")

        surface = pygame.Surface((60, 80))
        surface.fill(WHITE)
        start_pos = (10, 10)

        # These rects define each sprite's image area in the image_source.
        red_sprite_source = pygame.Rect((45, 0), (5, 4))
        blue_sprite_source = pygame.Rect((0, 40), (20, 10))

        # Create a source image/surface.
        image_source = pygame.Surface((50, 50))
        image_source.fill(YELLOW)
        image_source.fill(RED, red_sprite_source)
        image_source.fill(BLUE, blue_sprite_source)

        # The blue_sprite is stationary and will not reset its dirty flag. It
        # will be the non-dirty sprite in this test. Its values are dependent
        # on the use_source_rect flag.
        blue_sprite = pygame.sprite.DirtySprite(self.LG)

        if use_source_rect:
            blue_sprite.image = image_source
            # The rect is a bit smaller than the source_rect to make sure
            # LayeredDirty.draw() is using the correct dimensions.
            blue_sprite.rect = pygame.Rect(
                start_pos, (blue_sprite_source.w - 7, blue_sprite_source.h - 7)
            )
            blue_sprite.source_rect = blue_sprite_source
            start_x, start_y = blue_sprite.rect.topleft
            end_x = start_x + blue_sprite.source_rect.w
            end_y = start_y + blue_sprite.source_rect.h
        else:
            blue_sprite.image = image_source.subsurface(blue_sprite_source)
            blue_sprite.rect = pygame.Rect(start_pos, blue_sprite_source.size)
            start_x, start_y = blue_sprite.rect.topleft
            end_x, end_y = blue_sprite.rect.bottomright

        # The red_sprite is moving and will always be dirty.
        red_sprite = pygame.sprite.DirtySprite(self.LG)
        red_sprite.image = image_source
        red_sprite.rect = pygame.Rect(start_pos, red_sprite_source.size)
        red_sprite.source_rect = red_sprite_source
        red_sprite.dirty = 2

        # Draw the red_sprite as it moves a few steps.
        for _ in range(4):
            red_sprite.rect.move_ip(2, 1)

            # This is the method being tested.
            self.LG.draw(surface)

        # Check colors where the blue_sprite is drawn. We expect red where the
        # red_sprite is drawn over the blue_sprite, but the rest should be
        # blue.
        surface.lock()  # Lock surface for possible speed up.
        try:
            for y in range(start_y, end_y):
                for x in range(start_x, end_x):
                    if red_sprite.rect.collidepoint(x, y):
                        expected_color = RED
                    else:
                        expected_color = BLUE

                    color = surface.get_at((x, y))

                    self.assertEqual(color, expected_color, f"pos=({x}, {y})")
        finally:
            surface.unlock()

    def test_nondirty_intersections_redrawn(self):
        """Ensure non-dirty sprites are correctly redrawn
        when dirty sprites intersect with them.
        """
        self._nondirty_intersections_redrawn()

    def test_nondirty_intersections_redrawn__with_source_rect(self):
        """Ensure non-dirty sprites using source_rects are correctly redrawn
        when dirty sprites intersect with them.

        Related to issue #898.
        """
        self._nondirty_intersections_redrawn(True)


############################### SPRITE BASE CLASS ##############################
#
# tests common between sprite classes


class SpriteBase:
    def setUp(self):
        self.groups = []
        for Group in self.Groups:
            self.groups.append(Group())

        self.sprite = self.Sprite()

    def test_add_internal(self):
        for g in self.groups:
            self.sprite.add_internal(g)

        for g in self.groups:
            self.assertIn(g, self.sprite.groups())

    def test_remove_internal(self):
        for g in self.groups:
            self.sprite.add_internal(g)

        for g in self.groups:
            self.sprite.remove_internal(g)

        for g in self.groups:
            self.assertFalse(g in self.sprite.groups())

    def test_update(self):
        # What does this and the next test actually test?
        class test_sprite(pygame.sprite.Sprite):
            sink = []

            def __init__(self, *groups):
                pygame.sprite.Sprite.__init__(self, *groups)

            def update(self, *args):
                self.sink += args

        s = test_sprite()
        s.update(1, 2, 3)

        self.assertEqual(test_sprite.sink, [1, 2, 3])

    def test_update_with_kwargs(self):
        class test_sprite(pygame.sprite.Sprite):
            sink = []
            sink_dict = {}

            def __init__(self, *groups):
                pygame.sprite.Sprite.__init__(self, *groups)

            def update(self, *args, **kwargs):
                self.sink += args
                self.sink_dict.update(kwargs)

        s = test_sprite()
        s.update(1, 2, 3, foo=4, bar=5)

        self.assertEqual(test_sprite.sink, [1, 2, 3])
        self.assertEqual(test_sprite.sink_dict, {"foo": 4, "bar": 5})

    def test___init____added_to_groups_passed(self):
        expected_groups = sorted(self.groups, key=id)
        sprite = self.Sprite(self.groups)
        groups = sorted(sprite.groups(), key=id)

        self.assertListEqual(groups, expected_groups)

    def test_add(self):
        expected_groups = sorted(self.groups, key=id)
        self.sprite.add(self.groups)
        groups = sorted(self.sprite.groups(), key=id)

        self.assertListEqual(groups, expected_groups)

    def test_alive(self):
        self.assertFalse(
            self.sprite.alive(), "Sprite should not be alive if in no groups"
        )

        self.sprite.add(self.groups)

        self.assertTrue(self.sprite.alive())

    def test_groups(self):
        for i, g in enumerate(self.groups):
            expected_groups = sorted(self.groups[: i + 1], key=id)
            self.sprite.add(g)
            groups = sorted(self.sprite.groups(), key=id)

            self.assertListEqual(groups, expected_groups)

    def test_kill(self):
        self.sprite.add(self.groups)

        self.assertTrue(self.sprite.alive())

        self.sprite.kill()

        self.assertListEqual(self.sprite.groups(), [])
        self.assertFalse(self.sprite.alive())

    def test_remove(self):
        self.sprite.add(self.groups)
        self.sprite.remove(self.groups)

        self.assertListEqual(self.sprite.groups(), [])


############################## SPRITE CLASS TESTS ##############################


class SpriteTypeTest(SpriteBase, unittest.TestCase):
    Sprite = sprite.Sprite

    Groups = [
        sprite.Group,
        sprite.LayeredUpdates,
        sprite.RenderUpdates,
        sprite.OrderedUpdates,
    ]


class DirtySpriteTypeTest(SpriteBase, unittest.TestCase):
    Sprite = sprite.DirtySprite

    Groups = [
        sprite.Group,
        sprite.LayeredUpdates,
        sprite.RenderUpdates,
        sprite.OrderedUpdates,
        sprite.LayeredDirty,
    ]


class WeakSpriteTypeTest(SpriteTypeTest):
    Sprite = sprite.WeakSprite

    def test_weak_group_ref(self):
        """
        We create a list of groups, add them to the sprite.
        When we then delete the groups, the sprite should be "dead"
        """
        import gc

        groups = [Group() for Group in self.Groups]
        self.sprite.add(groups)
        del groups
        gc.collect()
        self.assertFalse(self.sprite.alive())


class DirtyWeakSpriteTypeTest(DirtySpriteTypeTest, WeakSpriteTypeTest):
    Sprite = sprite.WeakDirtySprite


############################## BUG TESTS #######################################


class SingleGroupBugsTest(unittest.TestCase):
    def test_memoryleak_bug(self):
        # For memoryleak bug posted to mailing list by Tobias Steinrücken on 16/11/10.
        # Fixed in revision 2953.

        import weakref
        import gc

        class MySprite(sprite.Sprite):
            def __init__(self, *args, **kwargs):
                sprite.Sprite.__init__(self, *args, **kwargs)
                self.image = pygame.Surface((2, 4), 0, 24)
                self.rect = self.image.get_rect()

        g = sprite.GroupSingle()
        screen = pygame.Surface((4, 8), 0, 24)
        s = MySprite()
        r = weakref.ref(s)
        g.sprite = s
        del s
        gc.collect()

        self.assertIsNotNone(r())

        g.update()
        g.draw(screen)
        g.sprite = MySprite()
        gc.collect()

        self.assertIsNone(r())


################################################################################

if __name__ == "__main__":
    unittest.main()
